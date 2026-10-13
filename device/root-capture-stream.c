/* Native capture-stream component, NOT a remount/service coordinator.
 * No live build/install/run approved. Production accepts only fixed p2 while ro.
 * Fixture builds cannot read block devices. No 256 MiB device-side staging.
 */
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/sysmacros.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef O_NOFOLLOW
#error O_NOFOLLOW required
#endif
#define CHUNK 65536
#define MAX_LINE 256
#ifdef NIMBUS_CAPTURE_FIXTURE
#define CAPTURE_BYTES 262144UL
#ifndef NIMBUS_FIXTURE_HASHER
#define NIMBUS_FIXTURE_HASHER "/usr/bin/sha256sum"
#endif
#else
#define CAPTURE_BYTES 268435456UL
#endif
static char base[1024] = "";
static unsigned char buffer[CHUNK];
static volatile sig_atomic_t aborted = 0;
static void cancel(int signum) { (void)signum; aborted = 1; }

static int path(char *out, size_t size, const char *suffix)
{
    int n = snprintf(out, size, "%s%s", base, suffix);
    return n > 0 && (size_t)n < size ? 0 : -1;
}

static int read_metadata(const char *suffix, char *out, size_t size)
{
    char name[1200];
    struct stat st;
    size_t pos = 0;
    int fd;
    if (path(name, sizeof(name), suffix)) return -1;
    fd = open(name, O_RDONLY | O_NOFOLLOW);
    if (fd < 0) return -1;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode)) { close(fd); return -1; }
    while (pos < size - 1 && !aborted) {
        ssize_t n = read(fd, out + pos, size - 1 - pos);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) { close(fd); return -1; }
        if (n == 0) break;
        pos += (size_t)n;
    }
    if (aborted || pos == size - 1) { close(fd); return -1; }
    out[pos] = '\0';
    close(fd);
    return 0;
}

static int safe_state(void)
{
    char text[16384], source[128], target[128], type[64], options[256];
    char *line, *save;
    unsigned int roots = 0, vfs_ro = 0;
    if (read_metadata("/sys/class/block/mmcblk0p2/dev", text, sizeof(text)) || strcmp(text, "179:2\n")) return -1;
    if (read_metadata("/sys/class/block/mmcblk0p2/start", text, sizeof(text)) || strcmp(text, "38912\n")) return -1;
    if (read_metadata("/sys/class/block/mmcblk0p2/size", text, sizeof(text))) return -1;
#ifdef NIMBUS_CAPTURE_FIXTURE
    if (strcmp(text, "512\n")) return -1;
#else
    if (strcmp(text, "524288\n")) return -1;
#endif
    if (read_metadata("/proc/modules", text, sizeof(text))) return -1;
    for (line = strtok_r(text, "\n", &save); line; line = strtok_r(NULL, "\n", &save))
        if (!strncmp(line, "g_file_storage ", 15)) return -1;
    if (read_metadata("/proc/mounts", text, sizeof(text))) return -1;
    for (line = strtok_r(text, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        if (sscanf(line, "%127s %127s %63s %255s", source, target, type, options) != 4) return -1;
        if (strcmp(target, "/")) continue;
        roots++;
        if ((strcmp(source, "/dev/root") && strcmp(source, "/dev/mmcblk0p2")) || strcmp(type, "ext3") ||
            strcmp(options, "ro,relatime,errors=continue,barrier=0,data=writeback")) return -1;
    }
    if (roots != 1 || read_metadata("/proc/self/mountinfo", text, sizeof(text))) return -1;
    for (line = strtok_r(text, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        char device[64], root[128], mountpoint[128], flags[128], *sep;
        if (sscanf(line, "%*u %*u %63s %127s %127s %127s", device, root, mountpoint, flags) != 4) return -1;
        if (strcmp(mountpoint, "/")) continue;
        vfs_ro++;
        sep = strstr(line, " - ");
        if (strcmp(device, "179:2") || strcmp(root, "/") || strcmp(flags, "ro,relatime") || !sep ||
            sscanf(sep + 3, "%63s %127s %255s", type, source, options) != 3 || strcmp(type, "ext3") ||
            (strcmp(source, "/dev/root") && strcmp(source, "/dev/mmcblk0p2")) ||
            strcmp(options, "ro,errors=continue,barrier=0,data=writeback")) return -1;
    }
    return vfs_ro == 1 ? 0 : -1;
}

static int write_all(int fd, const void *data, size_t size)
{
    const unsigned char *p = data;
    while (size) {
        if (aborted) return -1;
        ssize_t n = write(fd, p, size);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        p += n; size -= (size_t)n;
    }
    return 0;
}

static int line_read(int fd, char *out, size_t size)
{
    size_t pos = 0;
    while (pos + 1 < size) {
        if (aborted) return -1;
        ssize_t n = read(fd, out + pos, 1);
        if (n < 0 && errno == EINTR) continue;
        if (n != 1) return -1;
        if (out[pos++] == '\n') { out[pos] = '\0'; return 0; }
    }
    return -1;
}

static int valid_token(const char *token)
{
    size_t i;
    if (strlen(token) != 64) return 0;
    for (i = 0; i < 64; i++)
        if (!((token[i] >= '0' && token[i] <= '9') || (token[i] >= 'a' && token[i] <= 'f'))) return 0;
    return 1;
}

int main(int argc, char **argv)
{
    int rootfd = -1, input[2] = {-1, -1}, output[2] = {-1, -1}, status, result = 1;
    int report = 0, cleanup_ok = 1;
    pid_t hasher = -1;
    pid_t waited;
    char name[1200], line[MAX_LINE], expected[MAX_LINE], digest[65];
    struct stat st;
    unsigned long remaining = CAPTURE_BYTES;
    struct sigaction action;
#ifdef NIMBUS_CAPTURE_FIXTURE
    if (argc != 4 || strlen(argv[3]) >= sizeof(base) || argv[3][0] != '/') return 2;
    strcpy(base, argv[3]);
#else
    if (argc != 3) return 2;
#endif
    report = !strcmp(argv[1], "--stream-evidence");
    if ((!report && strcmp(argv[1], "--stream")) || !valid_token(argv[2])) return 2;
    if (report && (fstat(4, &st) || !S_ISREG(st.st_mode) || st.st_uid != geteuid() ||
                   (st.st_mode & 0777) != 0600 || st.st_size != 0 ||
                   (fcntl(4, F_GETFL) & O_ACCMODE) != O_WRONLY)) return 2;
    memset(&action, 0, sizeof(action));
    action.sa_handler = cancel;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGTERM, &action, NULL) || sigaction(SIGHUP, &action, NULL) ||
        sigaction(SIGINT, &action, NULL)) return 1;
    if (safe_state()) { fputs("Capture stream prerequisite refused.\n", stderr); goto finish; }
    if (path(name, sizeof(name), "/dev/mmcblk0p2")) return 1;
    rootfd = open(name, O_RDONLY | O_NOFOLLOW);
    if (rootfd < 0 || fstat(rootfd, &st)) goto finish;
#ifdef NIMBUS_CAPTURE_FIXTURE
    if (!S_ISREG(st.st_mode) || st.st_size != (off_t)CAPTURE_BYTES) goto finish;
#else
    if (!S_ISBLK(st.st_mode) || major(st.st_rdev) != 179 || minor(st.st_rdev) != 2) goto finish;
#endif
    if (signal(SIGPIPE, SIG_IGN) == SIG_ERR) goto finish;
    if (pipe(input) || pipe(output)) goto finish;
    hasher = fork();
    if (hasher < 0) goto finish;
    if (hasher == 0) {
        if (dup2(input[0], STDIN_FILENO) < 0 || dup2(output[1], STDOUT_FILENO) < 0) _exit(127);
        close(rootfd); close(input[0]); close(input[1]); close(output[0]); close(output[1]);
        close(3);  /* Coordinator's extra protocol descriptor is not hash input. */
        if (report) close(4); /* Only reader parent can report its child reap. */
#ifdef NIMBUS_CAPTURE_FIXTURE
        execl(NIMBUS_FIXTURE_HASHER, "sha256sum", (char *)NULL);
#else
        /* Coordinator must first match this standalone executable's reviewed
         * hash/metadata. Vendor BusyBox does not provide the sha256sum applet. */
        execl("/usr/bin/sha256sum", "sha256sum", (char *)NULL);
#endif
        _exit(127);
    }
    close(input[0]); input[0] = -1;
    close(output[1]); output[1] = -1;
    snprintf(line, sizeof(line), "NIMBUS-ROOT-BEGIN %s %lu 179:2 ro\n", argv[2], CAPTURE_BYTES);
    if (write_all(STDOUT_FILENO, line, strlen(line))) goto finish;
    while (remaining) {
        size_t want = remaining < CHUNK ? (size_t)remaining : CHUNK;
        ssize_t n;
        if (safe_state()) goto finish;
        n = read(rootfd, buffer, want);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0 || (size_t)n > want) goto finish;
        if (write_all(STDOUT_FILENO, buffer, (size_t)n) || write_all(input[1], buffer, (size_t)n)) goto finish;
        remaining -= (unsigned long)n;
    }
    if (close(rootfd)) { cleanup_ok = 0; rootfd = -1; goto finish; }
    rootfd = -1;  /* No partition reader survives the ACK wait. */
    close(input[1]); input[1] = -1;
    if (line_read(output[0], line, sizeof(line)) || strlen(line) != 68 || strcmp(line + 64, "  -\n")) goto finish;
    memcpy(digest, line, 64); digest[64] = '\0';
    if (!valid_token(digest)) goto finish;
    do { waited = waitpid(hasher, &status, 0); } while (waited < 0 && errno == EINTR && !aborted);
    if (waited != hasher) goto finish;
    hasher = -1;
    if (aborted) goto finish;
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0 || safe_state()) goto finish;
    snprintf(line, sizeof(line), "NIMBUS-ROOT-END %s %s\n", argv[2], digest);
    if (write_all(STDOUT_FILENO, line, strlen(line))) goto finish;
    snprintf(expected, sizeof(expected), "NIMBUS-HOST-VERIFIED %s %s\n", argv[2], digest);
    if (line_read(STDIN_FILENO, line, sizeof(line)) || strcmp(line, expected) || safe_state()) goto finish;
    /* Coordinator owns restoration/final stdout marker. This helper cannot emit success. */
    result = 0;
finish:
    if (rootfd >= 0 && close(rootfd)) cleanup_ok = 0;
    if (input[0] >= 0) close(input[0]);
    if (input[1] >= 0) close(input[1]);
    if (output[0] >= 0) close(output[0]);
    if (output[1] >= 0) close(output[1]);
    if (hasher > 0) {
        /* Only our unreaped direct child; never name-based or historic-PID signaling. */
        kill(hasher, SIGTERM);
        do { waited = waitpid(hasher, &status, 0); } while (waited < 0 && errno == EINTR);
        if (waited != hasher) cleanup_ok = 0;
    }
    if (report && cleanup_ok) {
        size_t left;
        const char *p;
        snprintf(line, sizeof(line), "NIMBUS-CHILD-DRAIN %s reader-closed hasher-drained\n", argv[2]);
        p = line; left = strlen(line);
        /* Cancellation invalidates capture, but must not suppress cleanup evidence. */
        while (left) {
            ssize_t n = write(4, p, left);
            if (n < 0 && errno == EINTR) continue;
            if (n <= 0) { cleanup_ok = 0; break; }
            p += n; left -= (size_t)n;
        }
        if (cleanup_ok && fsync(4)) cleanup_ok = 0;
    }
    if (!cleanup_ok) result = 70; /* Unknown cleanup/evidence: prohibit writable restoration. */
    if (result) fputs("Capture stream failed; coordinator must invalidate and observe cleanup.\n", stderr);
    return result;
}
