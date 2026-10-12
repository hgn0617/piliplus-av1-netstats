#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <libavcodec/avcodec.h>
#include <libavutil/hwcontext.h>
#include <libavutil/pixdesc.h>

static enum AVPixelFormat pick_hw(AVCodecContext *ctx, const enum AVPixelFormat *formats) {
    for (; *formats != AV_PIX_FMT_NONE; formats++)
        if (*formats == AV_PIX_FMT_VIDEOTOOLBOX) return *formats;
    return AV_PIX_FMT_NONE; // A software fallback cannot pass this test.
}
static uint32_t read_le32(const unsigned char *p) {
    return p[0] | p[1]<<8 | p[2]<<16 | (uint32_t)p[3]<<24;
}
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *f = fopen(argv[1], "rb");
    unsigned char header[32];
    if (!f || fread(header,1,32,f)!=32 || header[0]!='D' || header[1]!='K') return 3;
    const AVCodec *codec = avcodec_find_decoder_by_name("av1");
    AVCodecContext *ctx = avcodec_alloc_context3(codec);
    ctx->get_format = pick_hw;
    ctx->thread_count = 1;
    int rc = av_hwdevice_ctx_create(&ctx->hw_device_ctx, AV_HWDEVICE_TYPE_VIDEOTOOLBOX, NULL, NULL, 0);
    if (rc < 0 || avcodec_open2(ctx, codec, NULL) < 0) return 4;
    AVFrame *frame = av_frame_alloc();
    AVPacket *packet = av_packet_alloc();
    int count = 0, hardware = 0;
    unsigned char chunk[12];
    while (fread(chunk,1,12,f)==12) {
        uint32_t size = read_le32(chunk);
        if (size>10000000 || av_new_packet(packet,size)<0) return 5;
        if (fread(packet->data,1,size,f)!=size) return 6;
        rc=avcodec_send_packet(ctx,packet);
        if(rc<0) {fprintf(stderr,"send_packet=%d\n",rc);return 7;}
        av_packet_unref(packet);
        while ((rc=avcodec_receive_frame(ctx,frame))>=0) {
            count++;hardware += frame->format == AV_PIX_FMT_VIDEOTOOLBOX;
            printf("frame=%d format=%s width=%d height=%d\n",count,av_get_pix_fmt_name(frame->format),frame->width,frame->height);
            av_frame_unref(frame);
        }
        if(rc!=AVERROR(EAGAIN)&&rc!=AVERROR_EOF) return 8;
    }
    fclose(f); av_packet_free(&packet); av_frame_free(&frame); avcodec_free_context(&ctx);
    printf("hardware_frames=%d total_frames=%d\n",hardware,count);
    return count>0 && count==hardware ? 0 : 9;
}
