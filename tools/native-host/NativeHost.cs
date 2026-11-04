using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace PixelsUndoNative
{
    internal static class Program
    {
        private static Process server;
        private static string appDir;

        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            try
            {
                appDir = Environment.GetEnvironmentVariable("PIXELSUNDO_APP_DIR");
                if (String.IsNullOrEmpty(appDir))
                    appDir = AppDomain.CurrentDomain.BaseDirectory;
                appDir = appDir.Trim().Trim('"');
                if (!appDir.EndsWith("\\"))
                    appDir += "\\";
                Environment.CurrentDirectory = Path.GetTempPath();
                Program.Log("host cwd set; appDir=" + appDir);
                if (RelocateIfNeeded()) return;
                if (!IsAscii(AppDomain.CurrentDomain.BaseDirectory))
                {
                    Fail("当前文件夹路径包含中文，Windows 窗口组件无法直接从这类路径启动。\n\n请双击同目录下的 PixelsUndo.bat，它会自动以兼容方式打开独立窗口。\n\n或者把整个 PixelsUndo 文件夹移动到纯英文路径（例如 C:\\PixelsUndo）后再双击 exe。");
                    return;
                }
                string appExe = Path.Combine(appDir, "PixelsUndo-app", "PixelsUndo.exe");
                if (!File.Exists(appExe))
                {
                    Fail("找不到 PixelsUndo-app\\PixelsUndo.exe。\n请保持压缩包解压后的目录结构完整。");
                    return;
                }

                int port = FreePort(8765);
                string url = "http://127.0.0.1:" + port + "/";
                server = StartServer(appExe, port);
                WaitForServer(port, 30000);

                Application.Run(new MainForm(url));
            }
            catch (Exception ex)
            {
                Fail("PixelsUndo 无法启动。\n\n" + ex.Message);
            }
            finally
            {
                StopServer();
            }
        }

        private static bool RelocateIfNeeded()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            if (IsAscii(baseDir)) return false;
            if (Environment.GetEnvironmentVariable("PIXELSUNDO_RELOCATED") == "1") return false;

            string tempRoot = Path.Combine(Path.GetTempPath(), "PixelsUndoHost");
            string host = Path.Combine(tempRoot, "PixelsUndo.exe");
            try
            {
                Directory.CreateDirectory(tempRoot);
                File.Copy(Application.ExecutablePath, host, true);
                foreach (string dll in Directory.GetFiles(baseDir, "*.dll"))
                    File.Copy(dll, Path.Combine(tempRoot, Path.GetFileName(dll)), true);
            }
            catch (Exception ex)
            {
                Program.Log("relocation copy failed: " + ex.Message);
            }
            if (!File.Exists(host))
            {
                string cmd = "/c mkdir \"" + tempRoot + "\" 2>nul & copy /Y \"" + Path.Combine(baseDir, "PixelsUndo.exe") + "\" \"" + host + "\" >nul & copy /Y \"" + baseDir + "*.dll\" \"" + tempRoot + "\\\" >nul";
                try
                {
                    ProcessStartInfo prep = new ProcessStartInfo("cmd.exe", cmd);
                    prep.UseShellExecute = false;
                    prep.CreateNoWindow = true;
                    prep.WorkingDirectory = baseDir;
                    Process p = Process.Start(prep);
                    p.WaitForExit(15000);
                }
                catch (Exception ex)
                {
                    Program.Log("relocation cmd failed: " + ex.Message);
                }
            }
            if (!File.Exists(host))
            {
                Program.Log("relocation failed: " + host);
                return false;
            }

            Program.Log("relaunch from " + host);
            ProcessStartInfo start = new ProcessStartInfo(host);
            start.UseShellExecute = false;
            start.WorkingDirectory = tempRoot;
            start.EnvironmentVariables["PIXELSUNDO_APP_DIR"] = baseDir;
            start.EnvironmentVariables["PIXELSUNDO_RELOCATED"] = "1";
            Process.Start(start);
            return true;
        }

        private static bool IsAscii(string value)
        {
            foreach (char c in value)
                if (c > 127) return false;
            return true;
        }

        private static Process StartServer(string exe, int port)
        {
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = exe;
            info.Arguments = "--server-only --no-browser --port " + port;
            info.WorkingDirectory = Path.GetDirectoryName(exe);
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.WindowStyle = ProcessWindowStyle.Hidden;
            return Process.Start(info);
        }

        private static int FreePort(int preferred)
        {
            for (int port = preferred; port < preferred + 40; port++)
            {
                try
                {
                    TcpListener listener = new TcpListener(IPAddress.Loopback, port);
                    listener.Start();
                    listener.Stop();
                    return port;
                }
                catch
                {
                }
            }
            throw new Exception("8765-8804 端口都被占用。");
        }

        private static void WaitForServer(int port, int timeoutMs)
        {
            string url = "http://127.0.0.1:" + port + "/api/health";
            Stopwatch watch = Stopwatch.StartNew();
            Exception last = null;
            while (watch.ElapsedMilliseconds < timeoutMs)
            {
                try
                {
                    HttpWebRequest request = (HttpWebRequest)WebRequest.Create(url);
                    request.Proxy = null;
                    request.Timeout = 1500;
                    using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                    {
                        if ((int)response.StatusCode == 200)
                        {
                            return;
                        }
                    }
                }
                catch (Exception ex)
                {
                    last = ex;
                }
                Thread.Sleep(250);
            }
            throw new Exception("本地服务启动超时。" + (last == null ? "" : "\n" + last.Message));
        }

        private static void StopServer()
        {
            try
            {
                if (server != null && !server.HasExited)
                {
                    server.Kill();
                    server.WaitForExit(3000);
                }
            }
            catch
            {
            }
        }

        internal static void Log(string message)
        {
            try
            {
                File.AppendAllText(Path.Combine(appDir ?? ".", "PixelsUndo-native.log"),
                    DateTime.Now.ToString("s") + "  " + message + "\r\n");
            }
            catch
            {
            }
        }

        private static void Fail(string message)
        {
            Log(message);
            MessageBox.Show(message, "PixelsUndo", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    internal sealed class MainForm : Form
    {
        private readonly string url;
        private Rectangle restoreBounds;
        private bool fullscreen;

        public MainForm(string url)
        {
            this.url = url;
            Text = "PixelsUndo · 像素画工作室";
            Width = 1440;
            Height = 920;
            MinimumSize = new Size(1024, 680);
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Color.FromArgb(8, 10, 14);
            KeyPreview = true;
            KeyDown += delegate(object sender, KeyEventArgs e)
            {
                if (e.KeyCode == Keys.F11) { ToggleFullscreen(); e.Handled = true; }
                else if (e.KeyCode == Keys.Escape && fullscreen) { ToggleFullscreen(); e.Handled = true; }
            };

            WebView2 view = new WebView2();
            Program.Log("webview control created");
            view.Dock = DockStyle.Fill;
            view.CreationProperties = new CoreWebView2CreationProperties();
            view.CreationProperties.UserDataFolder = Path.Combine(Path.GetTempPath(), "PixelsUndoWebView2-" + Process.GetCurrentProcess().Id);
            view.CoreWebView2InitializationCompleted += delegate(object sender, CoreWebView2InitializationCompletedEventArgs e)
            {
                Program.Log("webview init completed success=" + e.IsSuccess + (e.InitializationException == null ? "" : " " + e.InitializationException));
                if (e.IsSuccess)
                {
                    view.CoreWebView2.WebMessageReceived += delegate(object s2, CoreWebView2WebMessageReceivedEventArgs m)
                    {
                        string msg = m.TryGetWebMessageAsString();
                        if (msg == "toggle-fullscreen" || (msg == "escape-fullscreen" && fullscreen))
                            ToggleFullscreen();
                    };
                    view.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(
                        "document.addEventListener('keydown',function(e){if(e.key==='F11'){e.preventDefault();window.chrome.webview.postMessage('toggle-fullscreen');}if(e.key==='Escape'){window.chrome.webview.postMessage('escape-fullscreen');}});");
                }
            };            view.NavigationCompleted += delegate(object sender, CoreWebView2NavigationCompletedEventArgs e)
            {
                Program.Log("navigation completed success=" + e.IsSuccess + " " + e.WebErrorStatus);
            };
            view.Source = new Uri(this.url);
            Program.Log("source set " + this.url);
            Controls.Add(view);
            Program.Log("control added");
        }

        private void ToggleFullscreen()
        {
            if (!fullscreen)
            {
                restoreBounds = Bounds;
                FormBorderStyle = FormBorderStyle.None;
                WindowState = FormWindowState.Normal;
                Bounds = Screen.FromControl(this).Bounds;
                fullscreen = true;
            }
            else
            {
                FormBorderStyle = FormBorderStyle.Sizable;
                Bounds = restoreBounds;
                fullscreen = false;
            }
            Program.Log("fullscreen=" + fullscreen);
        }
    }
}


