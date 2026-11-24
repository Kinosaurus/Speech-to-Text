// Local testing helper. Uses the already-authorized ADB shell audio permissions.
// Default: initializes routes only. Optional self-test plays/captures our shell
// tone through loopback; never opens a physical microphone or feeds app speech.
import android.app.Application;
import android.app.Instrumentation;
import android.content.Context;
import android.content.ContextWrapper;
import android.content.AttributionSource;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioRecord;
import android.media.AudioTrack;
import android.os.Looper;
import android.os.SystemClock;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicBoolean;
import java.lang.reflect.Field;
import java.lang.reflect.Method;

public final class QuietAudioProbe {
    private static final class ShellContext extends ContextWrapper {
        ShellContext(Context base) { super(base); }
        @Override public String getPackageName() { return "com.android.shell"; }
        public String getOpPackageName() { return "com.android.shell"; }
        @Override public Context getApplicationContext() { return this; }
        @Override public AttributionSource getAttributionSource() {
            return new AttributionSource.Builder(android.os.Process.myUid())
                .setPackageName("com.android.shell").build();
        }
    }
    static Object call(Object object, String name, Class<?>[] types, Object... args) throws Exception {
        Method method = object.getClass().getDeclaredMethod(name, types);
        method.setAccessible(true);
        return method.invoke(object, args);
    }
    public static void main(String[] args) {
        try { probe(args); System.out.println("PROBE_RELEASED"); System.exit(0); }
        catch (Throwable failure) { failure.printStackTrace(System.err); System.exit(2); }
    }
    static Context shellContext() throws Exception {
        Looper.prepareMainLooper();
        Class<?> activity = Class.forName("android.app.ActivityThread");
        Object thread = activity.getDeclaredMethod("systemMain").invoke(null);
        Context system = (Context) activity.getDeclaredMethod("getSystemContext").invoke(thread);
        System.out.println("SYSTEM_CONTEXT_READY");
        Context context = new ShellContext(system.createPackageContext("com.android.shell", 0));
        Class<?> bindClass = Class.forName("android.app.ActivityThread$AppBindData");
        java.lang.reflect.Constructor<?> bindConstructor = bindClass.getDeclaredConstructor();
        bindConstructor.setAccessible(true);
        Object bindData = bindConstructor.newInstance();
        Field info = bindClass.getDeclaredField("appInfo");
        info.setAccessible(true);
        info.set(bindData, context.getApplicationInfo());
        Field bound = activity.getDeclaredField("mBoundApplication");
        bound.setAccessible(true);
        bound.set(thread, bindData);
        Application app = Instrumentation.newApplication(Application.class, context);
        Field initial = activity.getDeclaredField("mInitialApplication");
        initial.setAccessible(true);
        initial.set(thread, app);
        System.out.println("SHELL_CONTEXT_READY");
        System.out.println("ATTRIBUTION_PACKAGE=" + context.getAttributionSource().getPackageName());
        return context;
    }
    private static void probe(String[] args) throws Exception {
        System.out.println("PROBE_START physical_microphone=false; optional shell-only output self-test");
        Context context = shellContext();
        int uid = context.getPackageManager().getApplicationInfo(args[0], 0).uid;
        Class<?> ruleBuilder = Class.forName("android.media.audiopolicy.AudioMixingRule$Builder");
        Object builder = ruleBuilder.getConstructor().newInstance();
        call(builder, "setTargetMixRole", new Class<?>[]{int.class}, 1);
        for (int source : new int[]{0, 1, 6, 7, 9}) {
            AudioAttributes.Builder attributes = new AudioAttributes.Builder();
            call(attributes, "setCapturePreset", new Class<?>[]{int.class}, source);
            call(builder, "addMixRule", new Class<?>[]{int.class, Object.class}, 2, attributes.build());
        }
        call(builder, "addMixRule", new Class<?>[]{int.class, Object.class}, 4, Integer.valueOf(uid));
        Object rule = call(builder, "build", new Class<?>[]{});
        Class<?> mixBuilder = Class.forName("android.media.audiopolicy.AudioMix$Builder");
        Object mix = mixBuilder.getConstructor(rule.getClass()).newInstance(rule);
        AudioFormat format = new AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT)
            .setSampleRate(48000).setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).build();
        call(mix, "setFormat", new Class<?>[]{AudioFormat.class}, format);
        call(mix, "setRouteFlags", new Class<?>[]{int.class}, 2); // LOOP_BACK only, no speaker render.
        Object route = call(mix, "build", new Class<?>[]{});
        Object outputRuleBuilder = ruleBuilder.getConstructor().newInstance();
        call(outputRuleBuilder, "setTargetMixRole", new Class<?>[]{int.class}, 0);
        call(outputRuleBuilder, "addMixRule", new Class<?>[]{int.class, Object.class}, 4, Integer.valueOf(uid));
        Object outputRule = call(outputRuleBuilder, "build", new Class<?>[]{});
        Object outputMix = mixBuilder.getConstructor(outputRule.getClass()).newInstance(outputRule);
        call(outputMix, "setFormat", new Class<?>[]{AudioFormat.class}, format);
        call(outputMix, "setRouteFlags", new Class<?>[]{int.class}, 2);
        Object outputRoute = call(outputMix, "build", new Class<?>[]{});
        Class<?> policyBuilder = Class.forName("android.media.audiopolicy.AudioPolicy$Builder");
        Object policyConfig = policyBuilder.getConstructor(Context.class).newInstance(context);
        call(policyConfig, "addMix", new Class<?>[]{route.getClass()}, route);
        call(policyConfig, "addMix", new Class<?>[]{outputRoute.getClass()}, outputRoute);
        Object policy = call(policyConfig, "build", new Class<?>[]{});
        AudioManager manager = context.getSystemService(AudioManager.class);
        AudioTrack track = null;
        AudioRecord output = null;
        boolean registered = false;
        try {
            int result = (Integer) call(manager, "registerAudioPolicy", new Class<?>[]{policy.getClass()}, policy);
            if (result != 0) throw new IllegalStateException("Audio policy registration failed: " + result);
            registered = true;
            track = (AudioTrack) call(policy, "createAudioTrackSource", new Class<?>[]{route.getClass()}, route);
            if (track == null || track.getState() != AudioTrack.STATE_INITIALIZED)
                throw new IllegalStateException("Digital source did not initialize");
            output = (AudioRecord) call(policy, "createAudioRecordSink", new Class<?>[]{outputRoute.getClass()}, outputRoute);
            if (output == null || output.getState() != AudioRecord.STATE_INITIALIZED)
                throw new IllegalStateException("Digital output sink did not initialize");
            System.out.println("{\"target_uid\":" + uid + ",\"loopback_only\":true,\"digital_source_initialized\":true,\"digital_output_sink_initialized\":true,\"audio_played\":false,\"capture_started\":false,\"microphone_opened\":false}");
            if (args.length > 1 && args[1].equals("--self-test-output")) {
                if (!args[0].equals("com.android.shell"))
                    throw new IllegalArgumentException("Self-test must target our shell UID only");
                testOutput(output, format);
            }
        } finally {
            System.out.println("RELEASING_OUTPUT_SINK");
            if (output != null) output.release();
            System.out.println("RELEASING_INPUT_SOURCE");
            if (track != null) track.release();
            System.out.println("UNREGISTERING_POLICY");
            if (registered) call(manager, "unregisterAudioPolicy", new Class<?>[]{policy.getClass()}, policy);
        }
    }

    // Tests only our generated tone through our own loopback output route.
    // Does not start a physical microphone or feed either commercial app.
    private static void testOutput(AudioRecord sink, AudioFormat format) throws Exception {
        final AtomicLong samples = new AtomicLong();
        final AtomicLong energy = new AtomicLong();
        final AtomicLong peak = new AtomicLong();
        final AtomicLong readError = new AtomicLong();
        final AtomicBoolean running = new AtomicBoolean(true);
        System.out.println("SELF_TEST_BUILD_PLAYER");
        AudioTrack player = new AudioTrack.Builder()
            .setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
            .setAudioFormat(format).setTransferMode(AudioTrack.MODE_STREAM)
            .setBufferSizeInBytes(48000).build();
        Thread reader = new Thread(() -> {
            short[] buffer = new short[4096];
            while (running.get()) {
                int count = sink.read(buffer, 0, buffer.length, AudioRecord.READ_NON_BLOCKING);
                if (count < 0) { readError.set(count); break; }
                long sum = 0, max = 0;
                for (int i = 0; i < count; i++) {
                    sum += (long)buffer[i] * buffer[i];
                    max = Math.max(max, Math.abs((long)buffer[i]));
                }
                samples.addAndGet(count); energy.addAndGet(sum);
                peak.accumulateAndGet(max, Math::max);
                SystemClock.sleep(5);
            }
        }, "quiet-output-calibration");
        reader.setDaemon(true);
        try {
            System.out.println("SELF_TEST_START_LOOPBACK_CAPTURE");
            sink.startRecording();
            if (sink.getRoutedDevice() != null)
                System.out.println("OUTPUT_DEVICE_TYPE=" + sink.getRoutedDevice().getType());
            reader.start();
            System.out.println("SELF_TEST_PREPARE_TONE");
            short[] tone = new short[48000 * 2];
            for (int frame = 0; frame < 48000; frame++) {
                short value = (short)(1500 * Math.sin(2 * Math.PI * 997 * frame / 48000));
                tone[frame * 2] = value; tone[frame * 2 + 1] = value;
            }
            player.play();
            System.out.println("SELF_TEST_PLAY_TONE_LOOPBACK");
            int written = 0;
            long deadline = SystemClock.elapsedRealtime() + 4000;
            while (written < tone.length && SystemClock.elapsedRealtime() < deadline) {
                int count = player.write(tone, written, tone.length - written, AudioTrack.WRITE_NON_BLOCKING);
                if (count < 0) throw new IllegalStateException("Output write failed: " + count);
                written += count;
                SystemClock.sleep(5);
            }
            SystemClock.sleep(1200);
            running.set(false);
            reader.join(2000);
            double rms = Math.sqrt((double)energy.get() / Math.max(1, samples.get()));
            System.out.println("{\"self_test\":\"shell_output_only\",\"written_samples\":" + written
                + ",\"captured_samples\":" + samples.get() + ",\"peak\":" + peak.get()
                + ",\"rms\":" + rms + ",\"read_error\":" + readError.get()
                + ",\"signal_detected\":" + (peak.get() > 500) + "}");
            if (written != tone.length || readError.get() != 0 || peak.get() <= 500)
                throw new IllegalStateException("Quiet output signal calibration failed");
        } finally {
            running.set(false);
            System.out.println("SELF_TEST_RELEASE_PLAYER");
            player.release();
            System.out.println("SELF_TEST_STOP_SINK");
            if (sink.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING) sink.stop();
            reader.join(2000);
            System.out.println("SELF_TEST_FINISHED");
        }
    }
}
