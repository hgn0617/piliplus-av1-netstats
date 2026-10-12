#import <Foundation/Foundation.h>
#include <TargetConditionals.h>
#include <dlfcn.h>
#include <pthread.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "client.h"

// Preserve the original mpv implementation and expose its full API via re-export.
static int (*initialize_core)(mpv_handle *);
static void (*destroy_core)(mpv_handle *), (*terminate_core)(mpv_handle *);
static int (*get_core)(mpv_handle *, const char *, mpv_format, void *);
static char *(*get_string_core)(mpv_handle *, const char *);
static int (*set_core)(mpv_handle *, const char *, mpv_format, void *);
static int (*command_core)(mpv_handle *, const char *const *);
static void (*free_core)(void *);
static pthread_once_t resolve_once = PTHREAD_ONCE_INIT;
static pthread_mutex_t players_lock = PTHREAD_MUTEX_INITIALIZER;
static dispatch_source_t timer;
static dispatch_queue_t queue;
static NSString *const enabled_key = @"PiliPlusAV1.ShowNetworkOverlay";
static NSString *const scale_key = @"PiliPlusAV1.NetworkOverlayScale";
static NSString *const corner_key = @"PiliPlusAV1.NetworkOverlayCorner";

@interface PiliPlusNetworkPlayer : NSObject
@property(nonatomic) mpv_handle *handle;
@property(nonatomic, copy) NSString *lastASS;
@property(nonatomic) int lastResX;
@end
@implementation PiliPlusNetworkPlayer
@end
static NSMutableArray<PiliPlusNetworkPlayer *> *players;

static void resolve_core(void) {
    Dl_info location;
    if (!dladdr((void *)&mpv_initialize, &location) || !location.dli_fname) return;
    NSString *folder = [[NSString stringWithUTF8String:location.dli_fname] stringByDeletingLastPathComponent];
    NSString *path = [folder stringByAppendingPathComponent:@"../MpvCore.framework/MpvCore"];
    void *core = dlopen(path.fileSystemRepresentation, RTLD_NOW | RTLD_LOCAL);
    if (!core) return;
    initialize_core = dlsym(core, "mpv_initialize");
    destroy_core = dlsym(core, "mpv_destroy");
    terminate_core = dlsym(core, "mpv_terminate_destroy");
    get_core = dlsym(core, "mpv_get_property");
    get_string_core = dlsym(core, "mpv_get_property_string");
    set_core = dlsym(core, "mpv_set_property");
    command_core = dlsym(core, "mpv_command");
    free_core = dlsym(core, "mpv_free");
    players = [NSMutableArray array];
    queue = dispatch_queue_create("com.piliplus.network-overlay", DISPATCH_QUEUE_SERIAL);
    [[NSUserDefaults standardUserDefaults] registerDefaults:@{
        enabled_key: @YES, scale_key: @1.0, corner_key: @"top-right"
    }];
}

static double number(mpv_handle *handle, const char *key, double fallback) {
    double value;
    return get_core(handle, key, MPV_FORMAT_DOUBLE, &value) >= 0 && isfinite(value) ? value : fallback;
}

static BOOL flag(mpv_handle *handle, const char *key, BOOL fallback) {
    int value;
    return get_core(handle, key, MPV_FORMAT_FLAG, &value) >= 0 ? value != 0 : fallback;
}

static void publish(mpv_handle *handle, BOOL enabled, BOOL visible, double rate,
                    double buffer, BOOL buffering, double scale, NSString *corner) {
    char *keys[] = {"ready", "enabled", "visible", "bytes_per_second", "buffered_seconds", "buffering", "scale", "corner"};
    mpv_node values[8] = {0};
    values[0].format = MPV_FORMAT_FLAG; values[0].u.flag = 1;
    values[1].format = MPV_FORMAT_FLAG; values[1].u.flag = enabled;
    values[2].format = MPV_FORMAT_FLAG; values[2].u.flag = visible;
    values[3].format = MPV_FORMAT_DOUBLE; values[3].u.double_ = rate;
    values[4].format = buffer >= 0 ? MPV_FORMAT_DOUBLE : MPV_FORMAT_NONE; values[4].u.double_ = buffer;
    values[5].format = MPV_FORMAT_FLAG; values[5].u.flag = buffering;
    values[6].format = MPV_FORMAT_DOUBLE; values[6].u.double_ = scale;
    values[7].format = MPV_FORMAT_STRING; values[7].u.string = (char *)corner.UTF8String;
    mpv_node_list list = {.num = 8, .values = values, .keys = keys};
    mpv_node node = {.u.list = &list, .format = MPV_FORMAT_NODE_MAP};
    set_core(handle, "user-data/piliplus-network", MPV_FORMAT_NODE, &node);
}

static void update(PiliPlusNetworkPlayer *player) {
    mpv_handle *handle = player.handle;
    NSUserDefaults *preferences = NSUserDefaults.standardUserDefaults;
    BOOL enabled = [preferences boolForKey:enabled_key];
    double scale = [preferences doubleForKey:scale_key];
    if (!isfinite(scale) || scale < 0.7 || scale > 1.6) scale = 1.0;
    NSString *corner = [preferences stringForKey:corner_key];
    if (!corner || ![@[@"top-right", @"top-left", @"bottom-right", @"bottom-left"] containsObject:corner]) corner = @"top-right";
    double rate = MAX(0, number(handle, "cache-speed", 0));
    double buffer = number(handle, "demuxer-cache-duration", -1);
    BOOL buffering = flag(handle, "paused-for-cache", NO);
    double width = number(handle, "osd-width", 0), height = number(handle, "osd-height", 0);
    char *path = get_string_core(handle, "path");
    BOOL network = path && (!strncmp(path, "https://", 8) || !strncmp(path, "http://", 7) || !strncmp(path, "edl://", 6));
    if (path) free_core(path);
    char *video = get_string_core(handle, "video-format");
    BOOL visible = enabled && network && video && width > 0 && height > 0
        && !flag(handle, "idle-active", YES) && !flag(handle, "eof-reached", NO);
    if (video) free_core(video);
    publish(handle, enabled, visible, rate, buffer, buffering, scale, corner);
    if (!visible) {
        if (player.lastASS) {
            const char *remove[] = {"osd-overlay", "9755", "none", "", NULL};
            command_core(handle, remove); player.lastASS = nil;
        }
        return;
    }

    NSString *speed = rate >= 1e6 ? [NSString stringWithFormat:@"%.2f MB/s", rate / 1e6]
        : rate >= 1e3 ? [NSString stringWithFormat:@"%.0f KB/s", rate / 1e3]
        : [NSString stringWithFormat:@"%.0f B/s", rate];
    NSString *suffix = buffer >= 0 ? [NSString stringWithFormat:@" %.1fs", MAX(0, buffer)] : @" --";
    NSString *label = [@"Buf" stringByAppendingString:suffix];
    // A slightly larger base font suits a phone's small embedded video viewport.
    const double font = 30, resY = 720;
    int resX = MAX(1, (int)llround(width / height * resY));
    double speedWidth = speed.length * font * 0.602;
    double labelWidth = label.length * font * 0.602;
    double inlineWidth = 24 + speedWidth + 9 + labelWidth;
    double stackedWidth = 24 + MAX(speedWidth, labelWidth);
    double s = MIN(scale, MAX(0.7, (resX - 36) / stackedWidth));
    BOOL stacked = inlineWidth * s > resX - 36;
    double boxWidth = (stacked ? stackedWidth : inlineWidth) * s;
    double boxHeight = (stacked ? 74 : 39) * s;
    BOOL left = [corner hasSuffix:@"left"], bottom = [corner hasPrefix:@"bottom"];
    double x = left ? 18 : MAX(12, resX - boxWidth - 18);
    double y = bottom ? resY - boxHeight - 18 : 18;
    NSString *outline = [NSString stringWithFormat:@"\\bord%.2f\\shad0\\3c&H101010&\\3a&H35&", s];
    NSString *ass = [NSString stringWithFormat:
        @"{\\an7\\pos(%.1f,%.1f)\\fnMenlo\\fs%.1f%@\\1c&HCEC18B&}↓\n"
         "{\\an7\\pos(%.1f,%.1f)\\fnMenlo\\fs%.1f%@\\1c&HF8F6F2&}%@\n"
         "{\\an7\\pos(%.1f,%.1f)\\fnMenlo\\fs%.1f%@\\1c&H%@&}%@",
        x, y - 2*s, font*s, outline,
        x + 24*s, y, font*s, outline, speed,
        x + (stacked ? 24 : 24 + speedWidth + 9)*s, y + (stacked ? 37 : 0)*s,
        font*s, outline, buffering ? @"B9D8FF" : @"F8F6F2", label];
    if ([player.lastASS isEqualToString:ass] && player.lastResX == resX) return;
    char horizontal[32]; snprintf(horizontal, sizeof(horizontal), "%d", resX);
    const char *command[] = {"osd-overlay", "9755", "ass-events", ass.UTF8String, horizontal, "720", "30", "no", "no", NULL};
    if (command_core(handle, command) >= 0) { player.lastASS = ass; player.lastResX = resX; }
}

static void start_timer(void) {
    if (timer) return;
    timer = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, queue);
    dispatch_source_set_timer(timer, dispatch_time(DISPATCH_TIME_NOW, 100*NSEC_PER_MSEC), 500*NSEC_PER_MSEC, 50*NSEC_PER_MSEC);
    dispatch_source_set_event_handler(timer, ^{
        @autoreleasepool {
            pthread_mutex_lock(&players_lock);
            for (PiliPlusNetworkPlayer *player in players) update(player);
            pthread_mutex_unlock(&players_lock);
        }
    });
    dispatch_resume(timer);
}

int mpv_initialize(mpv_handle *handle) {
    pthread_once(&resolve_once, resolve_core);
    if (!initialize_core || !get_core || !get_string_core || !set_core || !command_core || !free_core) return MPV_ERROR_UNINITIALIZED;
    int result = initialize_core(handle);
    if (result >= 0) {
        PiliPlusNetworkPlayer *player = [PiliPlusNetworkPlayer new]; player.handle = handle;
        pthread_mutex_lock(&players_lock);
        [players addObject:player]; start_timer();
        pthread_mutex_unlock(&players_lock);
    }
    return result;
}

static void forget(mpv_handle *handle) {
    pthread_mutex_lock(&players_lock);
    for (NSInteger i = players.count - 1; i >= 0; i--) {
        if (players[i].handle == handle) [players removeObjectAtIndex:i];
    }
    if (players.count == 0 && timer) { dispatch_source_cancel(timer); timer = nil; }
    pthread_mutex_unlock(&players_lock);
}

void mpv_destroy(mpv_handle *handle) {
    pthread_once(&resolve_once, resolve_core); forget(handle);
    if (destroy_core) destroy_core(handle);
}

void mpv_terminate_destroy(mpv_handle *handle) {
    pthread_once(&resolve_once, resolve_core); forget(handle);
    if (terminate_core) terminate_core(handle);
}

#if !TARGET_OS_IPHONE
// Host-only test entry point. This is not included in the iPhone framework.
void piliplus_network_test_preferences(int enabled, double scale, const char *corner) {
    NSUserDefaults *preferences = NSUserDefaults.standardUserDefaults;
    [preferences setBool:enabled != 0 forKey:enabled_key];
    [preferences setDouble:scale forKey:scale_key];
    [preferences setObject:[NSString stringWithUTF8String:corner] forKey:corner_key];
}
#endif
