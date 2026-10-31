/* Small supervisor: start Qt and acquisition together, restore the exact desktop.
 * Build: arm-linux-gnueabihf-gcc -static -Os -Wall -Wextra fast_launcher.c
 *        -o device_guard_launcher
 */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define FB_BYTES (1024*600*2)
#define MAX_GUI 64
struct gui { pid_t pid; size_t len; char argv[4096]; };
static struct gui previous[MAX_GUI];
static int gui_count;
static volatile sig_atomic_t stopping;
static volatile sig_atomic_t requested_background;
static char base[PATH_MAX], runtime[PATH_MAX];

static void on_signal(int signum) {
    if(signum==SIGUSR1)requested_background=1;
    else if(signum==SIGUSR2)requested_background=0;
    else stopping=1;
}
static double mono(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec+t.tv_nsec/1e9; }
static ssize_t read_file(const char *name,char *buffer,size_t size) {
    int fd=open(name,O_RDONLY); if(fd<0)return -1;
    size_t used=0;
    while(used<size-1) {
        ssize_t n=read(fd,buffer+used,size-1-used);
        if(n>0)used+=(size_t)n;
        else if(n<0&&errno==EINTR)continue;
        else if(n<0){close(fd);return -1;}
        else break;
    }
    close(fd);buffer[used]=0;return (ssize_t)used;
}
static void write_pid(const char *name,pid_t pid) {
    char path[PATH_MAX]; snprintf(path,sizeof(path),"%s/%s",runtime,name);
    FILE *f=fopen(path,"w"); if(f){fprintf(f,"%d\n",pid);fclose(f);}
}
static void json_string(FILE *f,const char *s,size_t n) {
    fputc('"',f);
    for(size_t i=0;i<n;i++) {
        unsigned char c=(unsigned char)s[i];
        if(c=='"'||c=='\\'){fputc('\\',f);fputc(c,f);}
        else if(c<32)fprintf(f,"\\u%04x",c);
        else fputc(c,f);
    }
    fputc('"',f);
}
static void pause_desktop(void) {
    gui_count=0;
    DIR *dir=opendir("/proc"); if(!dir)return;
    struct dirent *entry; char path[128], argv[4096];
    char *maps=malloc(262144); if(!maps){closedir(dir);return;}
    while((entry=readdir(dir))&&gui_count<MAX_GUI) {
        pid_t pid=atoi(entry->d_name); if(pid<=1)continue;
        snprintf(path,sizeof(path),"/proc/%d/cmdline",pid);
        ssize_t n=read_file(path,argv,sizeof(argv));
        if(n<8||memcmp(argv,"/opt/ui/",8))continue;
        snprintf(path,sizeof(path),"/proc/%d/maps",pid);
        if(read_file(path,maps,262144)<0||!strstr(maps,"libQt5Gui"))continue;
        if(kill(pid,SIGSTOP)==0) {
            previous[gui_count].pid=pid;previous[gui_count].len=(size_t)n;
            memcpy(previous[gui_count].argv,argv,(size_t)n);gui_count++;
        }
    }
    free(maps);closedir(dir);
    snprintf(path,sizeof(path),"%s/previous_gui.json",runtime);
    FILE *f=fopen(path,"w");if(!f)return;
    fputc('[',f);
    for(int i=0;i<gui_count;i++) {
        if(i)fputc(',',f);
        fprintf(f,"{\"pid\":%d,\"argv\":",previous[i].pid);
        json_string(f,previous[i].argv,previous[i].len);fputc('}',f);
    }
    fputs("]\n",f);fclose(f);
}
static unsigned char *capture_fb(void){
    unsigned char *frame=malloc(FB_BYTES);if(!frame)return NULL;
    int fd=open("/dev/fb0",O_RDONLY);
    if(fd<0||read(fd,frame,FB_BYTES)!=FB_BYTES){free(frame);frame=NULL;}
    if(fd>=0)close(fd);
    return frame;
}
static void release_desktop(unsigned char **saved_fb){
    char path[PATH_MAX];
    if(*saved_fb){int fd=open("/dev/fb0",O_WRONLY);if(fd>=0){if(write(fd,*saved_fb,FB_BYTES)<0)perror("restore framebuffer");close(fd);}free(*saved_fb);*saved_fb=NULL;}
    for(int i=0;i<gui_count;i++) {
        char current[4096];snprintf(path,sizeof(path),"/proc/%d/cmdline",previous[i].pid);
        ssize_t n=read_file(path,current,sizeof(current));
        if(n==(ssize_t)previous[i].len&&!memcmp(current,previous[i].argv,(size_t)n))kill(previous[i].pid,SIGCONT);
    }
    gui_count=0;
    snprintf(path,sizeof(path),"%s/previous_gui.json",runtime);
    FILE *f=fopen(path,"w");if(f){fputs("[]\n",f);fclose(f);}
}
static void record_visibility(int background){
    char path[PATH_MAX];snprintf(path,sizeof(path),"%s/visibility.json",runtime);
    FILE *f=fopen(path,"w");if(f){fprintf(f,"{\"background\":%s}\n",background?"true":"false");fclose(f);}
}
static pid_t spawn(char *const argv[],const char *logname,int qt) {
    pid_t pid=fork();if(pid!=0)return pid;
    char path[PATH_MAX];snprintf(path,sizeof(path),"%s/%s",runtime,logname);
    int fd=open(path,O_WRONLY|O_CREAT|O_APPEND,0644);
    if(fd>=0){dup2(fd,STDOUT_FILENO);dup2(fd,STDERR_FILENO);if(fd>2)close(fd);}
    signal(SIGTERM,SIG_DFL);signal(SIGINT,SIG_DFL);
    setenv("TZ","CST-8",1);setenv("PYTHONIOENCODING","utf-8",1);
    if(qt) {
        setenv("QT_QUICK_BACKEND","software",1);
        setenv("QT_QPA_PLATFORM","linuxfb:tty=/dev/fb0",1);
        setenv("QT_QPA_FONTDIR","/usr/share/fonts/ttf",1);
        setenv("QT_QPA_FB_TSLIB","1",1);
        setenv("TSLIB_TSDEVICE","/dev/input/event1",1);
        setenv("DISPLAY",":0.0",1);
    }
    execv(argv[0],argv);perror("execv");_exit(127);
}
static void terminate(pid_t pid) {
    if(pid<=0)return;
    int status;pid_t result=waitpid(pid,&status,WNOHANG);
    if(result==pid||(result<0&&errno==ECHILD))return;
    kill(pid,SIGTERM);
    for(int i=0;i<60;i++) {
        result=waitpid(pid,&status,WNOHANG);
        if(result==pid||(result<0&&errno==ECHILD))return;
        usleep(50000);
    }
    kill(pid,SIGKILL);waitpid(pid,&status,0);
}
int main(int argc,char **argv) {
    int replay=0;
    if(argc==2&&!strcmp(argv[1],"--replay"))replay=1;
    else if(argc!=1){fprintf(stderr,"Usage: %s [--replay]\n",argv[0]);return 2;}
    double started=mono();
    ssize_t size=readlink("/proc/self/exe",base,sizeof(base)-1);
    if(size<0)return 1;
    base[size]=0;
    char *slash=strrchr(base,'/');if(!slash)return 1;*slash=0;
    if(chdir(base))return 1;
    snprintf(runtime,sizeof(runtime),"%s/runtime",base);mkdir(runtime,0755);
    char path[PATH_MAX];snprintf(path,sizeof(path),"%s/launcher.lock",runtime);
    int lock=open(path,O_CREAT|O_RDWR|O_CLOEXEC,0644);
    if(lock<0||flock(lock,LOCK_EX|LOCK_NB)){fputs("Device Guard already running or lock failed\n",stderr);return 1;}
    write_pid("launcher.pid",getpid());
    snprintf(path,sizeof(path),"%s/gui.pid",runtime);unlink(path);
    struct sigaction sa;memset(&sa,0,sizeof(sa));sa.sa_handler=on_signal;
    sigaction(SIGTERM,&sa,NULL);sigaction(SIGINT,&sa,NULL);
    sigaction(SIGUSR1,&sa,NULL);sigaction(SIGUSR2,&sa,NULL);
    pid_t backend=-1,view=-1;unsigned char *saved_fb=NULL;
    int exit_code=0;
    if(!replay&&access("/dev/icm20608",F_OK)&&!access("/home/root/driver/icm20608/icm20608.ko",R_OK)) {
        char *insmod[]={"/sbin/insmod","/home/root/driver/icm20608/icm20608.ko",NULL};
        pid_t loader=spawn(insmod,"backend.log",0);int status=1;
        if(loader<0||waitpid(loader,&status,0)<0||!WIFEXITED(status)||WEXITSTATUS(status)){exit_code=1;goto cleanup;}
    }
    char script[PATH_MAX],data[PATH_MAX],qml[PATH_MAX],native_view[PATH_MAX];
    snprintf(script,sizeof(script),"%s/run.py",base);
    snprintf(data,sizeof(data),"%s/%s",base,replay?"replay_data":"data");
    char *backend_args[]={"/usr/bin/python3",script,"--data",data,NULL,NULL,NULL};
    if(replay){backend_args[4]="--replay";backend_args[5]="--no-indicators";}
    backend=spawn(backend_args,"backend.log",0);
    if(backend<0){exit_code=1;goto cleanup;}
    double backend_spawned=mono()-started;
    pause_desktop();
    saved_fb=capture_fb();
    snprintf(qml,sizeof(qml),"%s/ui/Main.qml",base);
    snprintf(native_view,sizeof(native_view),"%s/device_guard_view",base);
    char *view_args[]={"/usr/bin/qmlscene",qml,NULL};
    if(!access(native_view,X_OK)){view_args[0]=native_view;view_args[1]=NULL;}
    view=spawn(view_args,"gui.log",1);
    if(view<0){exit_code=1;goto cleanup;}
    write_pid("gui.pid",view);
    snprintf(path,sizeof(path),"%s/startup_native.json",runtime);
    FILE *trace=fopen(path,"w");
    if(trace){fprintf(trace,"{\"backend_spawn_s\":%.4f,\"qml_spawn_s\":%.4f,\"paused_factory_gui_count\":%d,\"parallel\":true}\n",backend_spawned,mono()-started,gui_count);fclose(trace);}
    int background=0;record_visibility(background);
    while(!stopping) {
        if(requested_background!=background){
            if(requested_background){release_desktop(&saved_fb);background=1;}
            else{pause_desktop();saved_fb=capture_fb();background=0;}
            record_visibility(background);
        }
        int status;
        pid_t child=waitpid(-1,&status,WNOHANG);
        if(child==backend||child==view){
            if(WIFSIGNALED(status)||(WIFEXITED(status)&&WEXITSTATUS(status)))exit_code=1;
            break;
        }
        usleep(50000);
    }
cleanup:
    terminate(view);terminate(backend);
    int beep=open("/sys/class/leds/beep/brightness",O_WRONLY);
    if(beep>=0){if(write(beep,"0",1)<0)perror("beep off");close(beep);}
    release_desktop(&saved_fb);
    snprintf(path,sizeof(path),"%s/gui.pid",runtime);unlink(path);
    snprintf(path,sizeof(path),"%s/launcher.pid",runtime);unlink(path);
    close(lock);return exit_code;
}
