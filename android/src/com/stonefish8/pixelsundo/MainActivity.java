package com.stonefish8.pixelsundo;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

import java.io.OutputStream;

public class MainActivity extends Activity {
    private static final int FILE_CHOOSER = 1001;

    private WebView webView;
    private ProgressBar spinner;
    private ValueCallback<Uri[]> fileCallback;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.rgb(8, 10, 9));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(8, 10, 9));

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(false);
        settings.setUseWideViewPort(false);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                String host = uri.getHost();
                if (host != null && (host.endsWith("onrender.com")
                        || host.endsWith("github.io")
                        || host.endsWith("jsdelivr.net"))) {
                    return false;
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (Exception ignored) {
                }
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                spinner.setVisibility(View.GONE);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                if (fileCallback != null) {
                    fileCallback.onReceiveValue(null);
                }
                fileCallback = callback;
                Intent intent = params.createIntent();
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                try {
                    startActivityForResult(intent, FILE_CHOOSER);
                    return true;
                } catch (Exception error) {
                    fileCallback = null;
                    Toast.makeText(MainActivity.this, "无法打开图片选择器", Toast.LENGTH_SHORT).show();
                    return false;
                }
            }
        });

        webView.addJavascriptInterface(new Bridge(), "PixelsUndoAndroid");

        root.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        spinner = new ProgressBar(this);
        FrameLayout.LayoutParams spinnerParams = new FrameLayout.LayoutParams(120, 120);
        spinnerParams.gravity = Gravity.CENTER;
        root.addView(spinner, spinnerParams);

        setContentView(root);
        webView.loadUrl(getString(R.string.app_url));
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode != FILE_CHOOSER) {
            super.onActivityResult(requestCode, resultCode, data);
            return;
        }
        if (fileCallback == null) {
            return;
        }
        Uri[] results = null;
        if (resultCode == RESULT_OK && data != null) {
            if (data.getClipData() != null) {
                int count = data.getClipData().getItemCount();
                results = new Uri[count];
                for (int i = 0; i < count; i++) {
                    results[i] = data.getClipData().getItemAt(i).getUri();
                }
            } else if (data.getData() != null) {
                results = new Uri[]{data.getData()};
            }
        }
        fileCallback.onReceiveValue(results);
        fileCallback = null;
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    private class Bridge {
        @JavascriptInterface
        public void saveImage(String filename, String base64) {
            try {
                byte[] bytes = Base64.decode(base64, Base64.DEFAULT);
                String name = (filename == null || filename.trim().isEmpty())
                        ? "pixelsundo.png" : filename.trim();
                String mime = name.toLowerCase().endsWith(".jpg")
                        || name.toLowerCase().endsWith(".jpeg") ? "image/jpeg" : "image/png";

                ContentValues values = new ContentValues();
                values.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
                values.put(MediaStore.MediaColumns.MIME_TYPE, mime);
                values.put(MediaStore.MediaColumns.RELATIVE_PATH,
                        Environment.DIRECTORY_PICTURES + "/PixelsUndo");
                values.put(MediaStore.MediaColumns.IS_PENDING, 1);

                ContentResolver resolver = getContentResolver();
                Uri uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
                if (uri == null) {
                    throw new IllegalStateException("无法创建相册文件");
                }
                OutputStream out = resolver.openOutputStream(uri);
                if (out == null) {
                    throw new IllegalStateException("无法写入相册文件");
                }
                out.write(bytes);
                out.close();

                ContentValues done = new ContentValues();
                done.put(MediaStore.MediaColumns.IS_PENDING, 0);
                resolver.update(uri, done, null, null);

                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        Toast.makeText(MainActivity.this,
                                "已保存到相册 Pictures/PixelsUndo", Toast.LENGTH_LONG).show();
                    }
                });
            } catch (Exception error) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        Toast.makeText(MainActivity.this,
                                "保存失败：" + error.getMessage(), Toast.LENGTH_LONG).show();
                    }
                });
            }
        }

        @JavascriptInterface
        public void toast(String message) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    Toast.makeText(MainActivity.this, message, Toast.LENGTH_SHORT).show();
                }
            });
        }
    }
}
