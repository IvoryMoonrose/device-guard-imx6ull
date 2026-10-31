/* Loopback-only task broker. Idle desktop command requests sleep in select(). */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define ROOT "/opt/device_guard/system_theme"
#define MAX_APPS 32
#define MAX_CLIENTS 24
struct app {char program[64],label[128],icon[256];int recent,running;};
struct client {int fd,used,waiting,app;double deadline;char buffer[8192];};
static struct app apps[MAX_APPS];static int app_count,serial;
static struct client clients[MAX_CLIENTS];
static int queue[16],queue_count;
static int close_requested[MAX_APPS];
static int show_requested[MAX_APPS];
static volatile sig_atomic_t stopped;
static void stop(int s){(void)s;stopped=1;}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static int find_app(const char *program){for(int i=0;i<app_count;i++)if(!strcmp(apps[i].program,program))return i;return -1;}
static void json_string(FILE *f,const char *s){fputc('"',f);for(;*s;s++){unsigned char c=(unsigned char)*s;if(c=='"'||c=='\\')fputc('\\',f);if(c<32)fprintf(f,"\\u%04x",c);else fputc(c,f);}fputc('"',f);}
static void close_client(struct client *c){if(c->fd>=0)close(c->fd);c->fd=-1;c->used=0;c->waiting=0;}
static void send_json(struct client *c,const char *body,int status){
    char header[512];int n=snprintf(header,sizeof(header),"HTTP/1.1 %d OK\r\nContent-Type: application/json; charset=utf-8\r\nAccess-Control-Allow-Origin: *\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: %zu\r\n\r\n",status,strlen(body));
    /* Responses are bounded below 16K; sockets use a short send timeout. */
    const char *parts[]={header,body};size_t sizes[]={(size_t)n,strlen(body)};
    for(int part=0;part<2;part++){size_t offset=0;while(offset<sizes[part]){ssize_t written=send(c->fd,parts[part]+offset,sizes[part]-offset,MSG_NOSIGNAL);if(written>0)offset+=(size_t)written;else if(written<0&&errno==EINTR)continue;else break;}}
    close_client(c);
}
static int json_program(const char *body,char *out,size_t size){
    const char *p=strstr(body,"\"program\"");if(!p)return -1;p=strchr(p+9,':');if(!p)return -1;
    do{p++;}while(*p==' '||*p=='\t');if(*p!='"')return -1;p++;
    size_t n=0;while(*p&&*p!='"'){if(n+1>=size||!((*p>='a'&&*p<='z')||(*p>='0'&&*p<='9')||*p=='_'))return -1;out[n++]=*p++;}
    out[n]=0;return *p=='"'?find_app(out):-1;
}
static void save_recent(void){
    FILE *f=fopen(ROOT "/runtime/recent.new","w");if(!f)return;
    for(int i=0;i<app_count;i++)if(apps[i].recent)fprintf(f,"%s %d\n",apps[i].program,apps[i].recent);
    fflush(f);fsync(fileno(f));fclose(f);rename(ROOT "/runtime/recent.new",ROOT "/runtime/recent");
}
static void read_apps(void){
    const char *paths[]={"/opt/ui/src/ATK-IMX6U/apk1.cfg","/opt/ui/src/ATK-IMX6U/apk2.cfg","/opt/ui/src/ATK-IMX6U/apk3.cfg"};
    for(int p=0;p<3;p++){
        FILE *f=fopen(paths[p],"r");if(!f)continue;char icon[256],label[128],program[64];
        while(app_count<MAX_APPS&&fscanf(f,"%255s %127s %63s",icon,label,program)==3){if(find_app(program)>=0)continue;struct app *a=&apps[app_count++];strcpy(a->program,program);strcpy(a->label,label);snprintf(a->icon,sizeof(a->icon),"file:///opt/ui/src/%s",icon);}
        fclose(f);
    }
    FILE *f=fopen(ROOT "/runtime/recent","r");if(f){char program[64];int value;while(fscanf(f,"%63s %d",program,&value)==2){int i=find_app(program);if(i>=0&&value>0){apps[i].recent=value;if(value>serial)serial=value;}}fclose(f);}
}
static void running_apps(void){
    for(int i=0;i<app_count;i++)apps[i].running=0;
    DIR *dir=opendir("/proc");if(!dir)return;struct dirent *entry;
    while((entry=readdir(dir))){int pid=atoi(entry->d_name);if(pid<=1)continue;char path[128],cmd[1024];snprintf(path,sizeof(path),"/proc/%d/cmdline",pid);int fd=open(path,O_RDONLY);if(fd<0)continue;ssize_t n=read(fd,cmd,sizeof(cmd)-1);close(fd);if(n<=0)continue;cmd[n]=0;
        for(int i=0;i<app_count;i++){char expected[160];snprintf(expected,sizeof(expected),"/opt/ui/src/apps/%s",apps[i].program);if(!strcmp(cmd,expected))apps[i].running=1;}
        if(!strcmp(cmd,"/opt/device_guard/device_guard_launcher")){int i=find_app("device_guard");if(i>=0)apps[i].running=1;}
    }
    closedir(dir);
}
static int memory_available(void){
    FILE *f=fopen("/proc/meminfo","r");if(!f)return 0;
    char line[256];int value=0;
    while(fgets(line,sizeof(line),f))if(sscanf(line,"MemAvailable: %d kB",&value)==1)break;
    fclose(f);return value;
}
static int prepare_app(int index){running_apps();return apps[index].running||memory_available()>=98304;}
static int guard_signal(int sig){
    FILE *f=fopen("/opt/device_guard/runtime/launcher.pid","r");int pid=0;
    if(!f)return -1;
    int ok=fscanf(f,"%d",&pid);fclose(f);if(ok!=1||pid<=1)return -1;
    char path[128],cmd[256];snprintf(path,sizeof(path),"/proc/%d/cmdline",pid);
    int fd=open(path,O_RDONLY);if(fd<0)return -1;ssize_t n=read(fd,cmd,sizeof(cmd)-1);close(fd);
    if(n<=0)return -1;
    cmd[n]=0;
    if(strcmp(cmd,"/opt/device_guard/device_guard_launcher"))return -1;
    return kill(pid,sig);
}
static void tasks_json(struct client *c,const char *current){
    running_apps();char *body=NULL;size_t length=0;FILE *f=open_memstream(&body,&length);if(!f){send_json(c,"{}",500);return;}
    fputs("{\"tasks\":[",f);int order[MAX_APPS],count=0;
    for(int i=0;i<app_count;i++)if(apps[i].recent||apps[i].running||!strcmp(apps[i].program,current))order[count++]=i;
    for(int i=0;i<count;i++)for(int j=i+1;j<count;j++){int a=order[i],b=order[j];int sa=(!strcmp(apps[a].program,current)?1000000:0)+apps[a].recent,sb=(!strcmp(apps[b].program,current)?1000000:0)+apps[b].recent;if(sb>sa){order[i]=b;order[j]=a;}}
    for(int k=0;k<count;k++){struct app *a=&apps[order[k]];if(k)fputc(',',f);fputs("{\"program\":",f);json_string(f,a->program);fputs(",\"label\":",f);json_string(f,a->label);fputs(",\"icon\":",f);json_string(f,a->icon);fprintf(f,",\"running\":%s,\"current\":%s}",a->running?"true":"false",!strcmp(a->program,current)?"true":"false");}
    fputs("]}",f);fclose(f);send_json(c,body,200);free(body);
}
static void command_reply(struct client *c){
    char body[256];int index=queue[0];memmove(queue,queue+1,(size_t)(--queue_count)*sizeof(int));
    if(index<0)snprintf(body,sizeof(body),"{\"desktop\":true}");
    else snprintf(body,sizeof(body),"{\"program\":\"%s\"}",apps[index].program);
    send_json(c,body,200);
}
static void handle(struct client *c){
    c->buffer[c->used]=0;char *end=strstr(c->buffer,"\r\n\r\n");if(!end)return;
    int length=0;char *size=strcasestr(c->buffer,"\r\nContent-Length:");if(size)length=atoi(size+17);
    if(length<0||length>4096){send_json(c,"{}",413);return;}
    if(c->used<(int)(end+4-c->buffer)+length)return;
    char method[8],path[256];if(sscanf(c->buffer,"%7s %255s",method,path)!=2){close_client(c);return;}
    char program[64]="";const char *body=end+4;
    if(!strcmp(path,"/health")){send_json(c,"{\"ok\":true,\"version\":1}",200);return;}
    if(!strncmp(path,"/tasks",6)){char *query=strstr(path,"current=");if(query)snprintf(program,sizeof(program),"%s",query+8);tasks_json(c,program);return;}
    if(!strncmp(path,"/appcommand?program=",20)){
        int index=find_app(path+20);if(index<0){send_json(c,"{}",400);return;}
        c->app=index;
        if(close_requested[index]){close_requested[index]=0;send_json(c,"{\"command\":\"close\"}",200);}
        else if(show_requested[index]){show_requested[index]=0;send_json(c,"{\"command\":\"show\"}",200);}
        else{c->waiting=2;c->deadline=now()+25;}
        return;
    }
    if(!strcmp(path,"/command")){if(queue_count)command_reply(c);else{c->waiting=1;c->deadline=now()+25;}return;}
    if(strcmp(method,"POST")){send_json(c,"{}",404);return;}
    int index=json_program(body,program,sizeof(program));if(index<0){send_json(c,"{\"error\":\"unknown app\"}",400);return;}
    if(!strcmp(path,"/prepare")){
        if(!prepare_app(index)){send_json(c,"{\"error\":\"内存不足，请在任务页结束不用的应用\"}",409);return;}
        if(!strcmp(program,"device_guard")&&apps[index].running){send_json(c,"{\"allowed\":true,\"resumed\":true}",200);return;}
        send_json(c,"{\"allowed\":true}",200);return;
    }
    if(!strcmp(path,"/close")){
        running_apps();if(apps[index].running)close_requested[index]=1;
        send_json(c,"{\"ok\":true}",200);return;
    }
    if(!strcmp(path,"/show")){
        if(strcmp(program,"device_guard")||guard_signal(SIGUSR2)){send_json(c,"{}",503);return;}
        show_requested[index]=1;send_json(c,"{\"ok\":true}",200);return;
    }
    if(!strcmp(path,"/background")||!strcmp(path,"/foreground")){
        if(strcmp(program,"device_guard")||guard_signal(!strcmp(path,"/background")?SIGUSR1:SIGUSR2))send_json(c,"{}",503);
        else{if(!strcmp(path,"/background")&&queue_count<16)queue[queue_count++]=-1;send_json(c,"{\"ok\":true}",200);}
        return;
    }
    if(!strcmp(path,"/activity")||!strcmp(path,"/activate")){
        if(!strcmp(path,"/activate")&&!prepare_app(index)){send_json(c,"{\"error\":\"内存不足，请在任务页结束不用的应用\"}",409);return;}
        apps[index].recent=++serial;save_recent();
        if(!strcmp(path,"/activate")){if(queue_count>=16){send_json(c,"{}",503);return;}queue[queue_count++]=index;}
        send_json(c,"{\"ok\":true}",200);return;
    }
    send_json(c,"{}",404);
}
int main(void){
    mkdir(ROOT "/runtime",0755);int lock=open(ROOT "/runtime/nav.lock",O_CREAT|O_RDWR|O_CLOEXEC,0644);if(lock<0||flock(lock,LOCK_EX|LOCK_NB))return 1;
    int listener=socket(AF_INET,SOCK_STREAM,0),one=1;if(listener<0)return 2;setsockopt(listener,SOL_SOCKET,SO_REUSEADDR,&one,sizeof(one));
    struct sockaddr_in address;memset(&address,0,sizeof(address));address.sin_family=AF_INET;address.sin_port=htons(18767);address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    if(bind(listener,(struct sockaddr*)&address,sizeof(address))||listen(listener,16))return 3;
    fcntl(listener,F_SETFL,O_NONBLOCK);signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGPIPE,SIG_IGN);
    FILE *pid=fopen(ROOT "/runtime/nav.pid","w");if(pid){fprintf(pid,"%d\n",getpid());fclose(pid);}read_apps();
    for(int i=0;i<MAX_CLIENTS;i++)clients[i].fd=-1;
    while(!stopped){
        fd_set readers;FD_ZERO(&readers);FD_SET(listener,&readers);int largest=listener;
        for(int i=0;i<MAX_CLIENTS;i++)if(clients[i].fd>=0){FD_SET(clients[i].fd,&readers);if(clients[i].fd>largest)largest=clients[i].fd;}
        struct timeval timeout={1,0};int ready=select(largest+1,&readers,NULL,NULL,&timeout);if(ready<0){if(errno==EINTR)continue;break;}
        if(FD_ISSET(listener,&readers)){int fd=accept(listener,NULL,NULL);if(fd>=0){int slot=-1;for(int i=0;i<MAX_CLIENTS;i++)if(clients[i].fd<0){slot=i;break;}if(slot<0)close(fd);else{struct timeval send_timeout={0,200000};setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&send_timeout,sizeof(send_timeout));clients[slot].fd=fd;clients[slot].used=0;clients[slot].waiting=0;clients[slot].deadline=now()+3;}}}
        for(int i=0;i<MAX_CLIENTS;i++){struct client *c=&clients[i];if(c->fd<0)continue;
            if(FD_ISSET(c->fd,&readers)){ssize_t n=recv(c->fd,c->buffer+c->used,sizeof(c->buffer)-1-(size_t)c->used,MSG_DONTWAIT);if(n>0){c->used+=(int)n;if(c->used>8000)send_json(c,"{}",413);else if(!c->waiting)handle(c);}else if(n==0||(n<0&&errno!=EAGAIN&&errno!=EINTR)){close_client(c);}}
            if(c->fd<0)continue;
            if(c->waiting==1&&queue_count)command_reply(c);
            else if(c->waiting==2&&close_requested[c->app]){close_requested[c->app]=0;send_json(c,"{\"command\":\"close\"}",200);}
            else if(c->waiting==2&&show_requested[c->app]){show_requested[c->app]=0;send_json(c,"{\"command\":\"show\"}",200);}
            else if(now()>c->deadline){if(c->waiting)send_json(c,"{}",200);else close_client(c);}
        }
    }
    for(int i=0;i<MAX_CLIENTS;i++)close_client(&clients[i]);
    close(listener);unlink(ROOT "/runtime/nav.pid");close(lock);return 0;
}
