package dev.upscaler.probe;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;

/** Phase 0.5 spike: can an app process load the vendor GPU/TPU libraries? */
public class MainActivity extends Activity {
    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        for (String name : new String[] {"OpenCL", "OpenCL-pixel", "edgetpu_client.google"}) {
            try { System.loadLibrary(name); Log.i("PROBE", "OK   loadLibrary " + name); }
            catch (Throwable t) { Log.w("PROBE", "FAIL loadLibrary " + name + ": " + t.getMessage()); }
        }
        finish();
    }
}
