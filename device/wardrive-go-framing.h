/* Bounded opaque GO framing only. No JSON/auth/radio/transport implementation.
 * Successful batches may be dispatched only by a separately reviewed handler.
 */
#ifndef NIMBUS_GO_FRAMING_H
#define NIMBUS_GO_FRAMING_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define GO_FRAME_MAX 2048U
#define GO_FRAME_CHUNK (GO_FRAME_MAX+4U)
#define GO_FRAME_BATCH 8U
#define GO_FRAME_TOTAL 4096U
typedef struct {
    unsigned char pending[GO_FRAME_CHUNK];
    size_t used;
    uint32_t length;
    unsigned int total;
    int failed;
} go_frames;
typedef struct {
    unsigned char payload[GO_FRAME_BATCH][GO_FRAME_MAX];
    size_t length[GO_FRAME_BATCH];
    unsigned int count;
} go_frame_batch;

static void go_frames_init(go_frames *state)
{ memset(state,0,sizeof(*state)); }

static int go_frames_refuse(go_frames *state,go_frame_batch *batch)
{
    memset(state->pending,0,sizeof(state->pending));
    state->used=0;state->length=0;state->failed=1;
    if (batch) memset(batch,0,sizeof(*batch));
    return -1;
}

static int go_frames_feed(go_frames *state,const unsigned char *data,size_t bytes,
                          go_frame_batch *batch)
{
    size_t index;
    if (!state || !batch) return -1;
    memset(batch,0,sizeof(*batch));
    if (state->failed || bytes>GO_FRAME_CHUNK || (!data && bytes))
        return go_frames_refuse(state,batch);
    for (index=0;index<bytes;index++) {
        state->pending[state->used++]=data[index];
        if (state->used<4) continue;
        if (state->used==4) {
            state->length=((uint32_t)state->pending[0]<<24)|
                ((uint32_t)state->pending[1]<<16)|
                ((uint32_t)state->pending[2]<<8)|state->pending[3];
            if (!state->length || state->length>GO_FRAME_MAX)
                return go_frames_refuse(state,batch);
        }
        if (state->used==4+state->length) {
            if (batch->count==GO_FRAME_BATCH || state->total==GO_FRAME_TOTAL)
                return go_frames_refuse(state,batch);
            memcpy(batch->payload[batch->count],state->pending+4,state->length);
            batch->length[batch->count++]=state->length;state->total++;
            memset(state->pending,0,sizeof(state->pending));state->used=0;state->length=0;
        }
    }
    return 0;
}

static int go_frames_finish(go_frames *state)
{
    if (!state) return -1;
    if (state->failed || state->used) return go_frames_refuse(state,NULL);
    return 0;
}
#endif
