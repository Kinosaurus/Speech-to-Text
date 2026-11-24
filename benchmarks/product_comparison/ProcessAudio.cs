// Windows process-only loopback capture using Microsoft's documented
// VAD\Process_Loopback activation API. Never captures the system microphone.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Diagnostics;

[StructLayout(LayoutKind.Sequential)] struct Blob { public uint Size; public IntPtr Data; }
[StructLayout(LayoutKind.Explicit)] struct Variant {
    [FieldOffset(0)] public ushort Type;
    [FieldOffset(8)] public Blob Blob;
}
[StructLayout(LayoutKind.Sequential)] struct Activation { public int Type; public uint Pid; public int Mode; }
[StructLayout(LayoutKind.Sequential, Pack=2)] struct WaveFormat {
    public ushort Tag, Channels; public uint Rate, BytesPerSecond;
    public ushort Align, Bits, Extra;
}
[ComImport, Guid("72A22D78-CDE4-431D-B8CC-843A71199B6D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IActivationOperation { [PreserveSig] int GetActivateResult(out int hr, [MarshalAs(UnmanagedType.IUnknown)] out object result); }
[Guid("41D949AB-9862-444A-80F6-C261334DA5EB"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown), ComVisible(true)]
public interface IActivationHandler { [PreserveSig] int ActivateCompleted(IActivationOperation operation); }
[Guid("94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown), ComVisible(true)]
public interface IAgileMarker { }
[ComImport, Guid("1CB9AD4C-DBFA-4C32-B178-C2F568A703B2"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioClient {
    [PreserveSig] int Initialize(int mode, uint flags, long duration, long periodicity, ref WaveFormat format, IntPtr guid);
    [PreserveSig] int GetBufferSize(out uint size);
    [PreserveSig] int GetStreamLatency(out long latency);
    [PreserveSig] int GetCurrentPadding(out uint padding);
    [PreserveSig] int IsFormatSupported(int mode, IntPtr format, out IntPtr closest);
    [PreserveSig] int GetMixFormat(out IntPtr format);
    [PreserveSig] int GetDevicePeriod(out long def, out long min);
    [PreserveSig] int Start(); [PreserveSig] int Stop(); [PreserveSig] int Reset();
    [PreserveSig] int SetEventHandle(IntPtr handle);
    [PreserveSig] int GetService(ref Guid iid, [MarshalAs(UnmanagedType.IUnknown)] out object service);
}
[ComImport, Guid("C8ADBD64-E71E-48A0-A4DE-185C395CD317"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioCaptureClient {
    [PreserveSig] int GetBuffer(out IntPtr data, out uint frames, out uint flags, out ulong position, out ulong qpc);
    [PreserveSig] int ReleaseBuffer(uint frames);
    [PreserveSig] int GetNextPacketSize(out uint frames);
}
[ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IDevices {
    [PreserveSig] int EnumAudioEndpoints(int flow,uint state,out IntPtr collection);
    [PreserveSig] int GetDefaultAudioEndpoint(int flow,int role,out IDevice device);
    [PreserveSig] int GetDevice([MarshalAs(UnmanagedType.LPWStr)]string id,out IDevice device);
}
[ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IDevice {
    [PreserveSig] int Activate(ref Guid iid,uint context,IntPtr parameters,[MarshalAs(UnmanagedType.IUnknown)] out object obj);
    [PreserveSig] int OpenPropertyStore(uint mode,out IntPtr store);
    [PreserveSig] int GetId([MarshalAs(UnmanagedType.LPWStr)]out string id);
}
[ComImport, Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IEndpointVolume {
    [PreserveSig] int RegisterControlChangeNotify(IntPtr callback);
    [PreserveSig] int UnregisterControlChangeNotify(IntPtr callback);
    [PreserveSig] int GetChannelCount(out uint count);
    [PreserveSig] int SetMasterVolumeLevel(float value,ref Guid context);
    [PreserveSig] int SetMasterVolumeLevelScalar(float value,ref Guid context);
    [PreserveSig] int GetMasterVolumeLevel(out float value);
    [PreserveSig] int GetMasterVolumeLevelScalar(out float value);
    [PreserveSig] int SetChannelVolumeLevel(uint channel,float value,ref Guid context);
    [PreserveSig] int SetChannelVolumeLevelScalar(uint channel,float value,ref Guid context);
    [PreserveSig] int GetChannelVolumeLevel(uint channel,out float value);
    [PreserveSig] int GetChannelVolumeLevelScalar(uint channel,out float value);
    [PreserveSig] int SetMute([MarshalAs(UnmanagedType.Bool)]bool mute,ref Guid context);
    [PreserveSig] int GetMute([MarshalAs(UnmanagedType.Bool)]out bool mute);
}
[ComImport, Guid("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ISessions {
    [PreserveSig] int GetAudioSessionControl(IntPtr guid,uint flags,out IntPtr control);
    [PreserveSig] int GetSimpleAudioVolume(IntPtr guid,uint flags,out IntPtr volume);
    [PreserveSig] int GetSessionEnumerator(out ISessionEnumerator sessions);
}
[ComImport, Guid("E2F5BB11-0570-40CA-ACDD-3AA01277DEE8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ISessionEnumerator { [PreserveSig] int GetCount(out int count); [PreserveSig] int GetSession(int index,out ISession session); }
[ComImport, Guid("BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ISession {
    [PreserveSig] int GetState(out int state);
    [PreserveSig] int GetDisplayName([MarshalAs(UnmanagedType.LPWStr)]out string name);
    [PreserveSig] int SetDisplayName([MarshalAs(UnmanagedType.LPWStr)]string name,ref Guid context);
    [PreserveSig] int GetIconPath([MarshalAs(UnmanagedType.LPWStr)]out string path);
    [PreserveSig] int SetIconPath([MarshalAs(UnmanagedType.LPWStr)]string path,ref Guid context);
    [PreserveSig] int GetGroupingParam(out Guid grouping);
    [PreserveSig] int SetGroupingParam(ref Guid grouping,ref Guid context);
    [PreserveSig] int RegisterAudioSessionNotification(IntPtr events);
    [PreserveSig] int UnregisterAudioSessionNotification(IntPtr events);
    [PreserveSig] int GetSessionIdentifier([MarshalAs(UnmanagedType.LPWStr)]out string value);
    [PreserveSig] int GetSessionInstanceIdentifier([MarshalAs(UnmanagedType.LPWStr)]out string value);
    [PreserveSig] int GetProcessId(out uint pid);
}
[ComImport, Guid("87CE5498-68D6-44E5-9215-6DA47EF883D8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IVolume {
    [PreserveSig] int SetMasterVolume(float level,ref Guid context);
    [PreserveSig] int GetMasterVolume(out float level);
    [PreserveSig] int SetMute([MarshalAs(UnmanagedType.Bool)]bool mute,ref Guid context);
    [PreserveSig] int GetMute([MarshalAs(UnmanagedType.Bool)]out bool mute);
}
[ComVisible(true), ClassInterface(ClassInterfaceType.None)]
public class ActivationHandler : IActivationHandler, IAgileMarker {
    public ManualResetEvent Ready=new ManualResetEvent(false); public object Result; public int Error;
    public int ActivateCompleted(IActivationOperation operation) {
        int hr; object result; int call=operation.GetActivateResult(out hr,out result);
        Error=call<0?call:hr; Result=result; Ready.Set(); return 0;
    }
}
class ProcessAudio {
    [DllImport("Mmdevapi.dll",CharSet=CharSet.Unicode,ExactSpelling=true)]
    static extern int ActivateAudioInterfaceAsync(string device,ref Guid iid,ref Variant parameters,IActivationHandler handler,out IActivationOperation operation);
    static void Check(int hr) { Marshal.ThrowExceptionForHR(hr); }
    static void Mute(uint pid,bool mute) {
        var enumerator=(IDevices)Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")));
        IDevice device;Check(enumerator.GetDefaultAudioEndpoint(0,0,out device));
        Guid iid=typeof(ISessions).GUID;object obj;Check(device.Activate(ref iid,23,IntPtr.Zero,out obj));
        ISessionEnumerator sessions;Check(((ISessions)obj).GetSessionEnumerator(out sessions));int count;Check(sessions.GetCount(out count));int changed=0;
        for(int i=0;i<count;i++) { ISession session;Check(sessions.GetSession(i,out session));uint owner;Check(session.GetProcessId(out owner));
            if(owner==pid){Guid context=Guid.Empty;bool original;Check(((IVolume)session).GetMute(out original));Check(((IVolume)session).SetMute(mute,ref context));Console.WriteLine("ORIGINAL_SESSION_MUTE="+original);changed++;}}
        if(changed==0)throw new InvalidOperationException("No audio session found for the specified test PID");
        Console.WriteLine("MUTED_TEST_SESSIONS="+changed);
    }
    static void Endpoint(string encodedId,bool mute) {
        var enumerator=(IDevices)Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")));
        IDevice device;
        if(encodedId=="default")Check(enumerator.GetDefaultAudioEndpoint(0,0,out device));
        else Check(enumerator.GetDevice(System.Text.Encoding.UTF8.GetString(Convert.FromBase64String(encodedId)),out device));
        string id;Check(device.GetId(out id));Guid iid=typeof(IEndpointVolume).GUID;object obj;Check(device.Activate(ref iid,23,IntPtr.Zero,out obj));
        var volume=(IEndpointVolume)obj;bool original;Check(volume.GetMute(out original));Guid context=Guid.Empty;Check(volume.SetMute(mute,ref context));
        Console.WriteLine("ENDPOINT_ID="+Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(id)));
        Console.WriteLine("ORIGINAL_ENDPOINT_MUTE="+original);
    }
    static void Capture(uint pid,string prefix) {
        var activation=new Activation {Type=1,Pid=pid,Mode=0};IntPtr memory=Marshal.AllocHGlobal(Marshal.SizeOf(activation));
        IAudioClient client=null;IAudioCaptureClient capture=null;
        try {
            Marshal.StructureToPtr(activation,memory,false);var variant=new Variant {Type=65,Blob=new Blob {Size=(uint)Marshal.SizeOf(activation),Data=memory}};
            Guid iid=typeof(IAudioClient).GUID;var handler=new ActivationHandler();IActivationOperation operation;
            int activationHr=ActivateAudioInterfaceAsync("VAD\\Process_Loopback",ref iid,ref variant,handler,out operation);
            if(activationHr<0)throw new COMException("ActivateAudioInterfaceAsync",activationHr);
            if(!handler.Ready.WaitOne(10000))throw new TimeoutException("Audio activation did not finish");
            if(handler.Error<0)throw new COMException("GetActivateResult",handler.Error);client=(IAudioClient)handler.Result;
            var format=new WaveFormat {Tag=1,Channels=2,Rate=44100,BytesPerSecond=176400,Align=4,Bits=16,Extra=0};
            Check(client.Initialize(0,0x80020000,0,0,ref format,IntPtr.Zero));iid=typeof(IAudioCaptureClient).GUID;object service;Check(client.GetService(ref iid,out service));capture=(IAudioCaptureClient)service;
            using(var data=new FileStream(prefix+".pcm",FileMode.CreateNew))
            using(var log=new StreamWriter(prefix+".jsonl",false)) {
                log.AutoFlush=true;Check(client.Start());Console.WriteLine("CAPTURE_READY pid="+pid);Console.Out.Flush();
                long first=Stopwatch.GetTimestamp(),framesRead=0;var stop=prefix+".stop";byte[] bytes=new byte[65536];
                while(!File.Exists(stop) && (Stopwatch.GetTimestamp()-first)/(double)Stopwatch.Frequency<180) {
                    uint available;Check(capture.GetNextPacketSize(out available));
                    while(available>0){IntPtr pointer;uint frames,flags;ulong position,qpc;Check(capture.GetBuffer(out pointer,out frames,out flags,out position,out qpc));
                        int size=checked((int)frames*4);if(bytes.Length<size)bytes=new byte[size];
                        if((flags&2)!=0)Array.Clear(bytes,0,size);else Marshal.Copy(pointer,bytes,0,size);
                        data.Write(bytes,0,size);log.WriteLine("{\"file_frame\":"+framesRead+",\"frames\":"+frames+",\"device_frame\":"+position+",\"qpc_100ns\":"+qpc+",\"flags\":"+flags+"}");
                        framesRead+=frames;Check(capture.ReleaseBuffer(frames));Check(capture.GetNextPacketSize(out available));}
                    Thread.Sleep(5);
                }
                Check(client.Stop());Console.WriteLine("CAPTURE_DONE frames="+framesRead);
            }
        }finally{if(capture!=null)Marshal.ReleaseComObject(capture);if(client!=null)Marshal.ReleaseComObject(client);Marshal.FreeHGlobal(memory);}
    }
    [MTAThread] static int Main(string[] args) {
        try {if(args[0]=="mute")Mute(UInt32.Parse(args[1]),args.Length<3||Boolean.Parse(args[2]));else if(args[0]=="endpoint")Endpoint(args[1],Boolean.Parse(args[2]));else if(args[0]=="capture")Capture(UInt32.Parse(args[1]),args[2]);else throw new ArgumentException("mode");return 0;}
        catch(Exception e){Console.Error.WriteLine(e);return 2;}
    }
}
