// Local ADB test harness. No root, no app-private data access.
// Input self-test refuses to read any PCM unless the device is REMOTE_SUBMIX.
// No device-wide privacy controls are changed, and no commercial app is started.
import android.content.Context;
import android.media.*;
import android.os.SystemClock;
import java.lang.reflect.*;
import java.util.concurrent.atomic.*;
import java.io.*;
import java.util.concurrent.TimeUnit;

public final class QuietAudioSession {
    static Object call(Object o, String n, Class<?>[] types, Object... args) throws Exception {
        return QuietAudioProbe.call(o, n, types, args);
    }
    static final AudioFormat FORMAT = new AudioFormat.Builder()
        .setEncoding(AudioFormat.ENCODING_PCM_16BIT).setSampleRate(48000)
        .setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).build();
    static Object makeMix(int uid, boolean input, boolean remoteOnly) throws Exception {
        Class<?> rb = Class.forName("android.media.audiopolicy.AudioMixingRule$Builder");
        Object b = rb.getConstructor().newInstance();
        call(b,"setTargetMixRole",new Class<?>[]{int.class},input?1:0);
        if (input) {
            for (int source : remoteOnly ? new int[]{8} : new int[]{0,1,5,6,7,9,10}) {
                AudioAttributes.Builder ab = new AudioAttributes.Builder();
                call(ab,"setCapturePreset",new Class<?>[]{int.class},source);
                call(b,"addMixRule",new Class<?>[]{int.class,Object.class},2,ab.build());
            }
        }
        call(b,"addMixRule",new Class<?>[]{int.class,Object.class},4,Integer.valueOf(uid));
        Object rule=call(b,"build",new Class<?>[]{});
        Class<?> mb=Class.forName("android.media.audiopolicy.AudioMix$Builder");
        Object mix=mb.getConstructor(rule.getClass()).newInstance(rule);
        call(mix,"setFormat",new Class<?>[]{AudioFormat.class},FORMAT);
        call(mix,"setRouteFlags",new Class<?>[]{int.class},2);
        return call(mix,"build",new Class<?>[]{});
    }
    static Object policy(Context context,Object... mixes) throws Exception {
        Class<?> pb=Class.forName("android.media.audiopolicy.AudioPolicy$Builder");
        Object b=pb.getConstructor(Context.class).newInstance(context);
        for(Object mix:mixes) call(b,"addMix",new Class<?>[]{mix.getClass()},mix);
        return call(b,"build",new Class<?>[]{});
    }
    static boolean micPrivacy(Context context) throws Exception {
        Object manager=context.getSystemService("sensor_privacy");
        return (Boolean)call(manager,"isSensorPrivacyEnabled",new Class<?>[]{int.class},1);
    }
    static void inspect(Context context,int uid) throws Exception {
        System.out.println("{\"microphone_privacy_enabled\":"+micPrivacy(context)+"}");
        AudioManager manager=context.getSystemService(AudioManager.class);
        int count=0;
        for(AudioRecordingConfiguration c:manager.getActiveRecordingConfigurations()) {
            int client=(Integer)call(c,"getClientUid",new Class<?>[]{});
            if(client!=uid) continue;
            count++;
            AudioDeviceInfo device=c.getAudioDevice();
            System.out.println("{\"recording_uid\":"+client+",\"source\":"+c.getClientAudioSource()
                +",\"silenced\":"+c.isClientSilenced()+",\"device_type\":"+(device==null?-1:device.getType())
                +",\"sample_rate\":"+c.getClientFormat().getSampleRate()+"}");
        }
        System.out.println("{\"active_target_recorders\":"+count+"}");
    }
    static void inputSelfTest(Context context) throws Exception {
        int uid=android.os.Process.myUid();
        Object mix=makeMix(uid,true,false);
        Object policy=policy(context,mix);
        AudioManager manager=context.getSystemService(AudioManager.class);
        AudioTrack source=null;
        AudioRecord recorder=null;
        boolean registered=false;
        AtomicBoolean running=new AtomicBoolean(true);
        AtomicLong peak=new AtomicLong(), samples=new AtomicLong(), errors=new AtomicLong();
        Thread reader=null;
        try {
            int status=(Integer)call(manager,"registerAudioPolicy",new Class<?>[]{policy.getClass()},policy);
            if(status!=0)throw new IllegalStateException("register="+status);
            registered=true;
            source=(AudioTrack)call(policy,"createAudioTrackSource",new Class<?>[]{mix.getClass()},mix);
            source.play();
            source.write(new short[9600],0,9600,AudioTrack.WRITE_NON_BLOCKING);
            SystemClock.sleep(200);
            recorder=new AudioRecord.Builder().setAudioSource(6)
                .setAudioFormat(new AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(48000).setChannelMask(AudioFormat.CHANNEL_IN_STEREO).build())
                .setBufferSizeInBytes(48000).build();
            if(recorder.getState()!=AudioRecord.STATE_INITIALIZED)
                throw new IllegalStateException("Self-test recorder did not initialize");
            final AudioRecord sink=recorder;
            sink.startRecording();
            AudioDeviceInfo device=sink.getRoutedDevice();
            if(device==null || device.getType()!=25)throw new IllegalStateException("Expected remote-submix input");
            System.out.println("{\"self_test_input_device_type\":"+device.getType()+",\"source\":6}");
            reader=new Thread(()->{
                short[] buf=new short[4096];
                while(running.get()) {
                    int n=sink.read(buf,0,buf.length,AudioRecord.READ_NON_BLOCKING);
                    if(n<0){errors.set(n);break;}
                    samples.addAndGet(n);
                    for(int i=0;i<n;i++)peak.accumulateAndGet(Math.abs((long)buf[i]),Math::max);
                    SystemClock.sleep(5);
                }
            });
            reader.setDaemon(true);reader.start();source.play();
            short[] tone=new short[96000];
            for(int i=0;i<48000;i++)tone[2*i]=tone[2*i+1]=(short)(1500*Math.sin(2*Math.PI*997*i/48000));
            int written=0;long deadline=SystemClock.elapsedRealtime()+4000;
            while(written<tone.length && SystemClock.elapsedRealtime()<deadline) {
                int n=source.write(tone,written,tone.length-written,AudioTrack.WRITE_NON_BLOCKING);
                if(n<0)throw new IllegalStateException("write="+n);
                written+=n;SystemClock.sleep(5);
            }
            SystemClock.sleep(1000);running.set(false);reader.join(2000);
            System.out.println("{\"input_signal_samples\":"+samples.get()+",\"written_samples\":"+written
                +",\"peak\":"+peak.get()+",\"read_error\":"+errors.get()+"}");
            if(written!=tone.length || peak.get()<500 || errors.get()!=0)
                throw new IllegalStateException("Input injection signal calibration failed");
        } finally {
            running.set(false);
            if(source!=null)source.release();
            if(recorder!=null){if(recorder.getRecordingState()==AudioRecord.RECORDSTATE_RECORDING)recorder.stop();recorder.release();}
            if(reader!=null)reader.join(2000);
            if(registered)call(manager,"unregisterAudioPolicy",new Class<?>[]{policy.getClass()},policy);
        }
    }
    static boolean targetRoute(Context context,int uid,boolean requireActive) throws Exception {
        int count=0;
        for(AudioRecordingConfiguration c:context.getSystemService(AudioManager.class).getActiveRecordingConfigurations()) {
            if((Integer)call(c,"getClientUid",new Class<?>[]{})!=uid)continue;
            count++;
            AudioDeviceInfo d=c.getAudioDevice();
            if(d==null || d.getType()!=25 || c.isClientSilenced())return false;
        }
        return !requireActive || count>0;
    }
    static void hold(Context context,String packageName,String pcmPath,String prefix,String controlPath) throws Exception {
        if(!packageName.equals("com.noveleffect.book") && !packageName.equals("com.readmio.app"))
            throw new IllegalArgumentException("Only the two authorized test apps are supported");
        int uid=context.getPackageManager().getApplicationInfo(packageName,0).uid;
        Object inputMix=makeMix(uid,true,false),outputMix=makeMix(uid,false,false);
        Object policy=policy(context,inputMix,outputMix);
        AudioManager manager=context.getSystemService(AudioManager.class);
        AudioTrack source=null;AudioRecord sink=null;
        boolean registered=false;
        AtomicBoolean capturing=new AtomicBoolean(true);
        AtomicReference<Throwable> captureError=new AtomicReference<>();
        Thread capture=null;
        FileInputStream pcm=null;
        final PrintWriter log=new PrintWriter(new FileOutputStream(prefix+".jsonl"),true);
        try {
            int status=(Integer)call(manager,"registerAudioPolicy",new Class<?>[]{policy.getClass()},policy);
            if(status!=0)throw new IllegalStateException("register="+status);
            registered=true;
            source=(AudioTrack)call(policy,"createAudioTrackSource",new Class<?>[]{inputMix.getClass()},inputMix);
            sink=(AudioRecord)call(policy,"createAudioRecordSink",new Class<?>[]{outputMix.getClass()},outputMix);
            if(source==null || sink==null || source.getState()!=1 || sink.getState()!=1)
                throw new IllegalStateException("Audio route initialization failed");
            final AudioRecord output=sink;
            sink.startRecording();
            if(sink.getRoutedDevice()==null || sink.getRoutedDevice().getType()!=25)
                throw new IllegalStateException("Output capture is not remote submix");
            capture=new Thread(()->{
                long total=0;
                try(FileOutputStream file=new FileOutputStream(prefix+".output.pcm")) {
                    byte[] bytes=new byte[8192];AudioTimestamp ts=new AudioTimestamp();
                    while(capturing.get()) {
                        int n=output.read(bytes,0,bytes.length,AudioRecord.READ_NON_BLOCKING);
                        if(n<0)throw new IOException("capture read="+n);
                        if(n>0){file.write(bytes,0,n);total+=n;}
                        int t=output.getTimestamp(ts,0);
                        synchronized(log){log.println("{\"kind\":\"output_clock\",\"read_bytes\":"+total
                            +",\"timestamp_status\":"+t+",\"frame\":"+ts.framePosition+",\"nano\":"+ts.nanoTime+"}");}
                        SystemClock.sleep(10);
                    }
                }catch(Throwable error){captureError.set(error);}
            },"app-output-capture");
            capture.setDaemon(true);capture.start();source.play();
            System.out.println("SESSION_READY target_uid="+uid+" input=virtual output=loopback media_volume_must_be_zero");
            long began=SystemClock.elapsedRealtime(),endDeadline=Long.MAX_VALUE,accepted=0,nextCheck=0,nextClock=0;
            boolean playing=false,finished=false;
            byte[] silence=new byte[1920],chunk=silence;
            int offset=0,length=chunk.length;
            File start=new File(controlPath+".start"),stop=new File(controlPath+".stop");
            AudioTimestamp ts=new AudioTimestamp();
            while(SystemClock.elapsedRealtime()-began<180000 && !stop.exists()) {
                if(captureError.get()!=null)throw new IOException("Capture failed",captureError.get());
                long now=SystemClock.elapsedRealtime();
                if(now>=nextCheck) {
                    if(!targetRoute(context,uid,false))throw new IllegalStateException("Target recorder route is unsafe or silenced");
                    nextCheck=now+100;
                }
                if(!playing && start.exists()) {
                    if(!targetRoute(context,uid,true))throw new IllegalStateException("No active, unsilenced virtual target recorder");
                    pcm=new FileInputStream(pcmPath);playing=true;chunk=new byte[1920];offset=0;length=pcm.read(chunk);
                    synchronized(log){log.println("{\"kind\":\"source_start\",\"first_frame\":"+(accepted/4)+",\"wall_nano\":"+System.nanoTime()+"}");}
                    System.out.println("SOURCE_STARTED first_frame="+(accepted/4));
                }
                if(now>=nextClock && source.getTimestamp(ts)) {
                    synchronized(log){log.println("{\"kind\":\"source_clock\",\"accepted_bytes\":"+accepted
                        +",\"frame\":"+ts.framePosition+",\"nano\":"+ts.nanoTime+"}");}
                    nextClock=now+100;
                }
                int n=source.write(chunk,offset,length-offset,AudioTrack.WRITE_NON_BLOCKING);
                if(n<0)throw new IOException("source write="+n);
                accepted+=n;offset+=n;
                if(offset==length) {
                    offset=0;
                    if(playing && !finished) {
                        length=pcm.read(chunk);
                        if(length<0) {
                            finished=true;endDeadline=now+7000;chunk=silence;length=chunk.length;
                            synchronized(log){log.println("{\"kind\":\"source_eof\",\"last_frame\":"+(accepted/4)+"}");}
                            System.out.println("SOURCE_EOF");
                        }
                    }
                }
                if(finished && now>=endDeadline)break;
                SystemClock.sleep(5);
            }
            if(!playing || !finished)throw new IllegalStateException("Session ended before complete replay");
            System.out.println("REPLAY_COMPLETE");
        } finally {
            // Stop the app BEFORE removing its virtual mic route, so it cannot
            // fall back to the physical microphone during cleanup.
            Process stopApp=new ProcessBuilder("/system/bin/am","force-stop",packageName).start();
            if(!stopApp.waitFor(10,TimeUnit.SECONDS) || stopApp.exitValue()!=0)
                System.err.println("APP_STOP_FAILED");
            capturing.set(false);
            if(capture!=null)capture.join(3000);
            if(pcm!=null)pcm.close();
            if(source!=null)source.release();
            if(sink!=null){if(sink.getRecordingState()==AudioRecord.RECORDSTATE_RECORDING)sink.stop();sink.release();}
            if(registered)call(manager,"unregisterAudioPolicy",new Class<?>[]{policy.getClass()},policy);
            log.close();
        }
    }
    public static void main(String[] args) {
        try {
            Context context=QuietAudioProbe.shellContext();
            if(args[0].equals("input-self-test"))inputSelfTest(context);
            else if(args[0].equals("inspect"))inspect(context,context.getPackageManager().getApplicationInfo(args[1],0).uid);
            else if(args[0].equals("hold"))hold(context,args[1],args[2],args[3],args[4]);
            else throw new IllegalArgumentException("Unknown mode");
            System.out.println("SESSION_RELEASED");System.exit(0);
        } catch(Throwable error){error.printStackTrace(System.err);System.exit(2);}
    }
}
