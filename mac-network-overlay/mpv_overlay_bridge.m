#import <AppKit/AppKit.h>
#include <dlfcn.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <math.h>

typedef struct mpv_handle mpv_handle;
typedef int (*InitializeFn)(mpv_handle *);
typedef int (*OptionFn)(mpv_handle *, const char *, const char *);
typedef int (*CommandFn)(mpv_handle *, const char *const *);
typedef void (*DestroyFn)(mpv_handle *);
static InitializeFn initialize_core;
static OptionFn option_core;
static CommandFn command_core;
static DestroyFn destroy_core, terminate_core;
static char script_path[PATH_MAX];
static pthread_once_t core_once = PTHREAD_ONCE_INIT;
static pthread_mutex_t players_lock = PTHREAD_MUTEX_INITIALIZER;
static NSMutableArray<NSValue *> *players;
static NSString *const preference_key = @"PiliPlusAV1.ShowNetworkOverlay";
static NSString *const size_key = @"PiliPlusAV1.NetworkOverlayScale";
static NSString *const corner_key = @"PiliPlusAV1.NetworkOverlayCorner";

int mpv_initialize(mpv_handle *ctx);

static void resolve_core(void) {
    Dl_info info;
    if (!dladdr((const void *)&mpv_initialize, &info) || !info.dli_fname) return;
    char folder[PATH_MAX];
    snprintf(folder, sizeof(folder), "%s", info.dli_fname);
    char *slash = strrchr(folder, '/');
    if (!slash) return;
    *slash = 0;
    char core_path[PATH_MAX];
    snprintf(core_path, sizeof(core_path), "%s/MpvCore", folder);
    snprintf(script_path, sizeof(script_path), "%s/NetworkOverlay/network_overlay.lua", folder);
    void *core = dlopen(core_path, RTLD_NOW | RTLD_LOCAL);
    if (!core) return;
    initialize_core = (InitializeFn)dlsym(core, "mpv_initialize");
    option_core = (OptionFn)dlsym(core, "mpv_set_option_string");
    command_core = (CommandFn)dlsym(core, "mpv_command");
    destroy_core = (DestroyFn)dlsym(core, "mpv_destroy");
    terminate_core = (DestroyFn)dlsym(core, "mpv_terminate_destroy");
    players = [NSMutableArray array];
}

static BOOL overlay_enabled(void) {
    id value = [[NSUserDefaults standardUserDefaults] objectForKey:preference_key];
    return value == nil || [value boolValue];
}

static double overlay_scale(void) {
    double value = [[NSUserDefaults standardUserDefaults] doubleForKey:size_key];
    return value >= 0.7 && value <= 1.6 ? value : 1.0;
}

static NSString *overlay_corner(void) {
    NSString *value = [[NSUserDefaults standardUserDefaults] stringForKey:corner_key];
    return value && [@[@"top-right", @"top-left", @"bottom-right", @"bottom-left"] containsObject:value]
        ? value : @"top-right";
}

static void broadcast(const char *message, const char *value) {
    const char *args[] = {"script-message", message, value, NULL};
    pthread_mutex_lock(&players_lock);
    for (NSValue *player in players) command_core((mpv_handle *)player.pointerValue, args);
    pthread_mutex_unlock(&players_lock);
}

@interface PiliPlusNetworkOverlayMenu : NSObject
@property(nonatomic, strong) NSMenuItem *item;
@property(nonatomic, strong) NSArray<NSMenuItem *> *sizeItems;
@property(nonatomic, strong) NSArray<NSMenuItem *> *cornerItems;
- (void)toggle:(id)sender;
- (void)setSize:(NSMenuItem *)sender;
- (void)setCorner:(NSMenuItem *)sender;
@end

@implementation PiliPlusNetworkOverlayMenu
- (void)toggle:(id)sender {
    BOOL enabled = !overlay_enabled();
    [[NSUserDefaults standardUserDefaults] setBool:enabled forKey:preference_key];
    self.item.state = enabled ? NSControlStateValueOn : NSControlStateValueOff;
    broadcast("piliplus-network-set", enabled ? "yes" : "no");
}
- (void)setSize:(NSMenuItem *)sender {
    double value = [sender.representedObject doubleValue];
    [[NSUserDefaults standardUserDefaults] setDouble:value forKey:size_key];
    for (NSMenuItem *item in self.sizeItems) item.state = item == sender ? NSControlStateValueOn : NSControlStateValueOff;
    char text[32]; snprintf(text, sizeof(text), "%.2f", value);
    broadcast("piliplus-network-size", text);
}
- (void)setCorner:(NSMenuItem *)sender {
    NSString *value = sender.representedObject;
    [[NSUserDefaults standardUserDefaults] setObject:value forKey:corner_key];
    for (NSMenuItem *item in self.cornerItems) item.state = item == sender ? NSControlStateValueOn : NSControlStateValueOff;
    broadcast("piliplus-network-corner", value.UTF8String);
}
@end

static PiliPlusNetworkOverlayMenu *menu_controller;

static void install_menu(void) {
    dispatch_async(dispatch_get_main_queue(), ^{
        if (menu_controller || !NSApp || !NSApp.mainMenu) return;
        NSMenu *menu = NSApp.mainMenu.itemArray.firstObject.submenu;
        if (!menu) return;
        menu_controller = [PiliPlusNetworkOverlayMenu new];
        NSMenuItem *item = [[NSMenuItem alloc] initWithTitle:@"显示网速与缓冲" action:@selector(toggle:) keyEquivalent:@"n"];
        item.keyEquivalentModifierMask = NSEventModifierFlagCommand | NSEventModifierFlagShift;
        item.target = menu_controller;
        item.state = overlay_enabled() ? NSControlStateValueOn : NSControlStateValueOff;
        menu_controller.item = item;
        NSInteger index = MAX(0, menu.numberOfItems - 2);
        [menu insertItem:[NSMenuItem separatorItem] atIndex:index];
        [menu insertItem:item atIndex:index + 1];
        NSMenuItem *sizeRoot = [[NSMenuItem alloc] initWithTitle:@"网速显示字体大小" action:nil keyEquivalent:@""];
        sizeRoot.submenu = [[NSMenu alloc] initWithTitle:sizeRoot.title];
        NSMutableArray *sizes = [NSMutableArray array];
        NSArray *sizeValues = @[@0.8, @1.0, @1.25, @1.5];
        NSArray *sizeTitles = @[@"小", @"标准", @"大", @"特大"];
        for (NSUInteger i = 0; i < sizeValues.count; i++) {
            NSMenuItem *choice = [[NSMenuItem alloc] initWithTitle:sizeTitles[i] action:@selector(setSize:) keyEquivalent:@""];
            choice.target = menu_controller;
            choice.representedObject = sizeValues[i];
            choice.state = fabs([sizeValues[i] doubleValue] - overlay_scale()) < 0.01 ? NSControlStateValueOn : NSControlStateValueOff;
            [sizeRoot.submenu addItem:choice]; [sizes addObject:choice];
        }
        menu_controller.sizeItems = sizes;
        [menu insertItem:sizeRoot atIndex:index + 2];
        NSMenuItem *cornerRoot = [[NSMenuItem alloc] initWithTitle:@"网速显示位置" action:nil keyEquivalent:@""];
        cornerRoot.submenu = [[NSMenu alloc] initWithTitle:cornerRoot.title];
        NSMutableArray *corners = [NSMutableArray array];
        NSArray *cornerValues = @[@"top-right", @"top-left", @"bottom-right", @"bottom-left"];
        NSArray *cornerTitles = @[@"右上角", @"左上角", @"右下角", @"左下角"];
        for (NSUInteger i = 0; i < cornerValues.count; i++) {
            NSMenuItem *choice = [[NSMenuItem alloc] initWithTitle:cornerTitles[i] action:@selector(setCorner:) keyEquivalent:@""];
            choice.target = menu_controller;
            choice.representedObject = cornerValues[i];
            choice.state = [cornerValues[i] isEqualToString:overlay_corner()] ? NSControlStateValueOn : NSControlStateValueOff;
            [cornerRoot.submenu addItem:choice]; [corners addObject:choice];
        }
        menu_controller.cornerItems = corners;
        [menu insertItem:cornerRoot atIndex:index + 3];
    });
}

int mpv_initialize(mpv_handle *ctx) {
    pthread_once(&core_once, resolve_core);
    if (!initialize_core || !option_core || !command_core) return -20;
    const char *preference = overlay_enabled() ? "piliplus_net-enabled=yes" : "piliplus_net-enabled=no";
    option_core(ctx, "script-opts-append", preference);
    char scale[64]; snprintf(scale, sizeof(scale), "piliplus_net-scale=%.2f", overlay_scale());
    option_core(ctx, "script-opts-append", scale);
    NSString *corner = [@"piliplus_net-corner=" stringByAppendingString:overlay_corner()];
    option_core(ctx, "script-opts-append", corner.UTF8String);
    int result = initialize_core(ctx);
    if (result >= 0) {
        const char *args[] = {"load-script", script_path, NULL};
        command_core(ctx, args);
        pthread_mutex_lock(&players_lock);
        [players addObject:[NSValue valueWithPointer:ctx]];
        pthread_mutex_unlock(&players_lock);
        install_menu();
    }
    return result;
}

static void forget_player(mpv_handle *ctx) {
    pthread_mutex_lock(&players_lock);
    [players removeObject:[NSValue valueWithPointer:ctx]];
    pthread_mutex_unlock(&players_lock);
}

void mpv_destroy(mpv_handle *ctx) {
    pthread_once(&core_once, resolve_core);
    forget_player(ctx);
    if (destroy_core) destroy_core(ctx);
}

void mpv_terminate_destroy(mpv_handle *ctx) {
    pthread_once(&core_once, resolve_core);
    forget_player(ctx);
    if (terminate_core) terminate_core(ctx);
}
