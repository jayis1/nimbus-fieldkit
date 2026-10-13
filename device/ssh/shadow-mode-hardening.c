/* Permission-only shadow hardening. No password/account contents are written.
 * Expected identity/digest arrive on stdin, never argv/logs. Only --harden may
 * fchmod the held, verified regular inode to 0600. Failure never restores 0744.
 * Checks are sampled; no exclusion of concurrent privileged writers promised.
 */
#define _GNU_SOURCE
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../root-capture-sha256.h"

static int same_inode(const struct stat *a, const struct stat *b)
{ return a->st_dev==b->st_dev && a->st_ino==b->st_ino; }

static int safe_directory(const struct stat *st, uid_t owner, gid_t group)
{
    return S_ISDIR(st->st_mode) && st->st_uid==owner && st->st_gid==group &&
        (st->st_mode & 07777)==0755;
}

static int safe_file(const struct stat *st, uid_t owner, gid_t group,
                     uintmax_t device, uintmax_t inode, uintmax_t bytes)
{
    mode_t mode=st->st_mode & 07777;
    return S_ISREG(st->st_mode) && st->st_uid==owner && st->st_gid==group &&
        st->st_nlink==1 && st->st_size>0 && st->st_size<=65536 &&
        (uintmax_t)st->st_dev==device && (uintmax_t)st->st_ino==inode &&
        (uintmax_t)st->st_size==bytes && (mode==0744 || mode==0600);
}

static int pin(uintmax_t *device, uintmax_t *inode, uintmax_t *bytes, char hash[65])
{
    char input[256], *at, *end;
    size_t used=0, i;
    for (;;) {
        ssize_t n=read(STDIN_FILENO,input+used,sizeof(input)-used);
        if (n<0 && errno==EINTR) continue;
        if (n<0) return -1;
        if (!n) break;
        used+=(size_t)n;
        if (used>=sizeof(input)) return -1;
    }
    input[used]=0;
    if (used<12 || memcmp(input,"SHADOW-PIN ",11)!=0) return -1;
    at=input+11;
    for (i=0;i<3;i++) {
        uintmax_t value;
        if (*at<'0' || *at>'9') return -1;
        errno=0;value=strtoumax(at,&end,10);
        if (errno || end==at || *end!=' ') return -1;
        if (i==0) *device=value;
        if (i==1) *inode=value;
        if (i==2) *bytes=value;
        at=end+1;
    }
    if (!*inode || !*bytes || *bytes>65536 || strlen(at)!=65 || at[64]!='\n') return -1;
    for (i=0;i<64;i++) if (!((at[i]>='0' && at[i]<='9') || (at[i]>='a' && at[i]<='f'))) return -1;
    memcpy(hash,at,64);hash[64]=0;
    return 0;
}

static int current_path(int root, int directory, const struct stat *dir,
                        const struct stat *file, const char *name)
{
    struct stat now;
    if (root>=0 && (fstatat(root,"etc",&now,AT_SYMLINK_NOFOLLOW) ||
                   !S_ISDIR(now.st_mode) || !same_inode(&now,dir))) return -1;
    if (fstat(directory,&now) || !same_inode(&now,dir) ||
        now.st_uid!=dir->st_uid || now.st_gid!=dir->st_gid ||
        (now.st_mode & 07777)!=0755) return -1;
    if (fstatat(directory,name,&now,AT_SYMLINK_NOFOLLOW) ||
        !S_ISREG(now.st_mode) || !same_inode(&now,file)) return -1;
    return 0;
}

#ifdef SHADOW_FIXTURE
static int fixture_gate(void)
{
    const char *ready=getenv("SHADOW_FIXTURE_READY_FD"), *gate=getenv("SHADOW_FIXTURE_GATE_FD");
    char byte;
    if (!ready && !gate) return 0;
    if (!ready || !gate) return -1;
    if (write(atoi(ready),"R",1)!=1 || read(atoi(gate),&byte,1)!=1) return -1;
    return 0;
}
#endif

int main(int argc, char **argv)
{
    int root=-1, directory=-1, file=-1, result=2, hardened=0;
    int apply;
    const char *name="shadow";
    uid_t owner=0;
    gid_t group=0;
    uintmax_t device=0, inode=0, bytes=0;
    char expected[65], before[65], after[65];
    struct stat dir, initial, observed;
#ifdef SHADOW_FIXTURE
    if (argc!=3) return 2;
    owner=geteuid();group=getegid();
#else
    if (argc!=2 || geteuid()!=0) return 2;
#endif
    if (!strcmp(argv[1],"--check-backup") || !strcmp(argv[1],"--harden-backup")) name="shadow-";
    else if (strcmp(argv[1],"--check") && strcmp(argv[1],"--harden")) return 2;
    apply=!strcmp(argv[1],"--harden") || !strcmp(argv[1],"--harden-backup");
    if (pin(&device,&inode,&bytes,expected)) goto done;
#ifdef SHADOW_FIXTURE
    directory=open(argv[2],O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
#else
    root=open("/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if (root<0 || fstat(root,&observed) || !safe_directory(&observed,owner,group)) goto done;
    directory=openat(root,"etc",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
#endif
    if (directory<0 || fstat(directory,&dir) || !safe_directory(&dir,owner,group)) goto done;
    if (fstatat(directory,name,&observed,AT_SYMLINK_NOFOLLOW) ||
        !safe_file(&observed,owner,group,device,inode,bytes)) goto done;
    file=openat(directory,name,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
    if (file<0 || fstat(file,&initial) || !safe_file(&initial,owner,group,device,inode,bytes)) goto done;
    if (sha_file(file,before) || strcmp(before,expected) || fstat(file,&observed) ||
        !safe_file(&observed,owner,group,device,inode,bytes) || current_path(root,directory,&dir,&observed,name)) goto done;
    if (!apply) {
        printf("SHADOW-CHECK=PASS target=%s identity-and-bytes-matched no-mode-change native_auth_verified=no\n",name);
        result=0;goto done;
    }
#ifdef SHADOW_FIXTURE
    if (fixture_gate()) goto done;
#endif
    if ((initial.st_mode & 07777)!=0600) {
        if (fchmod(file,0600)) goto done;
        hardened=1;
    }
    if (fsync(file) || lseek(file,0,SEEK_SET)<0 || sha_file(file,after) ||
        strcmp(after,expected) || fstat(file,&observed) ||
        !safe_file(&observed,owner,group,device,inode,bytes) ||
        (observed.st_mode & 07777)!=0600 || current_path(root,directory,&dir,&observed,name)) {
        result=3;goto done;
    }
    if (fsync(directory)) { result=3;goto done; }
    printf("SHADOW-HARDEN=PASS target=%s mode=0600 bytes-verified-unchanged=yes account-records-written=no persistence_verified=no\n",name);
    result=0;
done:
    if (file>=0) close(file);
    if (directory>=0) close(directory);
    if (root>=0) close(root);
    if (result) fputs(hardened || result==3 ?
        "Shadow hardening unconfirmed; mode may be 0600. Preserve evidence; never restore insecure permissions.\n" :
        "Shadow identity/metadata/digest check refused; no account content written.\n",stderr);
    memset(expected,0,sizeof(expected));memset(before,0,sizeof(before));memset(after,0,sizeof(after));
    return result;
}
