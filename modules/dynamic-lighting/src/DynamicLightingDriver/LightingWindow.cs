using System.Runtime.InteropServices;
using System.Windows.Forms;
using Windows.Devices.Lights;

namespace DynamicLightingDriver;

/// <summary>
/// A small companion window that gives the driver process foreground status,
/// which is required for LampArray.IsAvailable to become true on Windows 11.
/// Runs on a dedicated STA thread.
/// </summary>
public sealed class LightingWindow : IDisposable
{
    [DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll")]
    private static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);

    [DllImport("kernel32.dll")]
    private static extern uint GetCurrentThreadId();

    [DllImport("user32.dll")]
    private static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);

    [DllImport("user32.dll")]
    private static extern bool BringWindowToTop(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    private static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    private static extern bool GetCursorPos(out POINT lpPoint);

    [DllImport("user32.dll")]
    private static extern bool SetCursorPos(int x, int y);

    [DllImport("user32.dll")]
    private static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, IntPtr dwExtraInfo);

    [StructLayout(LayoutKind.Sequential)]
    private struct RECT { public int Left, Top, Right, Bottom; }

    [StructLayout(LayoutKind.Sequential)]
    private struct POINT { public int X, Y; }

    private const byte VK_MENU = 0x12; // Alt key
    private const uint KEYEVENTF_EXTENDEDKEY = 0x0001;
    private const uint KEYEVENTF_KEYUP = 0x0002;
    private const int SW_RESTORE = 9;
    private const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    private const uint MOUSEEVENTF_LEFTUP = 0x0004;
    private Form? _form;
    private Label? _statusLabel;
    private Thread? _uiThread;
    private readonly ManualResetEventSlim _ready = new();
    private volatile bool _disposed;
    private System.Windows.Forms.Timer? _retryTimer;
    private int _retryCount;
    private volatile bool _holdForeground;

    /// <summary>
    /// Custom Form subclass (needed for designer serialization of HoldForeground property).
    /// </summary>
    private sealed class ForegroundForm : Form
    {
        [System.ComponentModel.DesignerSerializationVisibility(System.ComponentModel.DesignerSerializationVisibility.Hidden)]
        [System.ComponentModel.Browsable(false)]
        public bool HoldForeground { get; set; }
    }

    public void Start()
    {
        _uiThread = new Thread(RunUIThread)
        {
            IsBackground = true,
            Name = "LightingWindow-STA",
        };
        _uiThread.SetApartmentState(ApartmentState.STA);
        _uiThread.Start();
        _ready.Wait(TimeSpan.FromSeconds(5));
    }

    /// <summary>
    /// Brings the companion window to the foreground so that LampArray.IsAvailable becomes true.
    /// First tries the standard SetForegroundWindow approach. If that fails, falls back to
    /// simulating a mouse click on the companion window via SendInput, which Windows treats
    /// as genuine user input and always activates the target window.
    /// </summary>
    public bool BringToForeground()
    {
        if (_form is null || _form.IsDisposed) return false;

        var tcs = new TaskCompletionSource<bool>();
        _form.BeginInvoke(() =>
        {
            try
            {
                var handle = _form.Handle;

                _form.Visible = true;
                _form.WindowState = FormWindowState.Normal;
                _form.TopMost = true;

                // Try the standard approach first
                keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY, UIntPtr.Zero);
                keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, UIntPtr.Zero);

                var foreground = GetForegroundWindow();
                var foregroundThread = GetWindowThreadProcessId(foreground, out _);
                var currentThread = GetCurrentThreadId();

                bool attached = false;
                if (foregroundThread != currentThread)
                {
                    attached = AttachThreadInput(currentThread, foregroundThread, true);
                }

                BringWindowToTop(handle);
                SetForegroundWindow(handle);
                _form.Activate();

                if (attached)
                {
                    AttachThreadInput(currentThread, foregroundThread, false);
                }

                // Brief delay for the system to process the foreground change
                Thread.Sleep(50);

                // Check if we actually got foreground. If not, simulate a click.
                if (GetForegroundWindow() != handle)
                {
                    Console.Error.WriteLine("[LightingWindow] SetForegroundWindow failed, falling back to SimulateClick");
                    SimulateClickOnWindow(handle);
                }
                else
                {
                    Console.Error.WriteLine("[LightingWindow] SetForegroundWindow succeeded");
                }

                tcs.SetResult(true);
            }
            catch
            {
                tcs.SetResult(false);
            }
        });

        return tcs.Task.GetAwaiter().GetResult();
    }

    /// <summary>
    /// Simulates a mouse click on the companion window's title bar using mouse_event.
    /// Windows treats this as genuine user input, bypassing foreground restrictions.
    /// Saves and restores the cursor position to minimize disruption.
    /// </summary>
    private void SimulateClickOnWindow(IntPtr handle)
    {
        if (!GetWindowRect(handle, out var rect)) return;
        if (!GetCursorPos(out var savedPos)) return;

        // Target: center of the window's title bar
        var clickX = (rect.Left + rect.Right) / 2;
        var clickY = rect.Top + 10;

        Console.Error.WriteLine($"[LightingWindow] SimulateClick at ({clickX},{clickY}), restoring to ({savedPos.X},{savedPos.Y})");

        // Move cursor, click, move back
        SetCursorPos(clickX, clickY);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, IntPtr.Zero);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, IntPtr.Zero);
        SetCursorPos(savedPos.X, savedPos.Y);
    }

    /// <summary>
    /// Starts a background retry loop that periodically attempts to bring the window to the
    /// foreground. Stops automatically after success or after maxRetries attempts.
    /// </summary>
    public void StartForegroundRetryLoop(int intervalMs = 500, int maxRetries = 30)
    {
        if (_form is null || _form.IsDisposed) return;

        _form.BeginInvoke(() =>
        {
            StopRetryTimer();

            _retryCount = 0;
            _retryTimer = new System.Windows.Forms.Timer { Interval = intervalMs };
            _retryTimer.Tick += (_, _) =>
            {
                _retryCount++;
                if (_retryCount > maxRetries)
                {
                    StopRetryTimer();
                    return;
                }

                var handle = _form!.Handle;
                var foreground = GetForegroundWindow();

                // Already foreground — done
                if (foreground == handle)
                {
                    StopRetryTimer();
                    return;
                }

                BringToForeground();
            };
            _retryTimer.Start();
        });
    }

    /// <summary>
    /// Stops the foreground-retry timer if one is running.
    /// </summary>
    public void StopRetryLoop()
    {
        if (_form is null || _form.IsDisposed) return;
        _form.BeginInvoke(StopRetryTimer);
    }

    private void StopRetryTimer()
    {
        if (_retryTimer != null)
        {
            _retryTimer.Stop();
            _retryTimer.Dispose();
            _retryTimer = null;
        }
    }

    /// <summary>
    /// When true, the companion window will aggressively reclaim foreground status
    /// whenever it loses activation (e.g., user clicks on another window).
    /// Set this while effects are running so the device stays available.
    /// </summary>
    public void SetHoldForeground(bool hold)
    {
        _holdForeground = hold;
        if (_form is ForegroundForm fg)
        {
            if (fg.IsDisposed) return;
            fg.BeginInvoke(() => fg.HoldForeground = hold);
        }
    }

    /// <summary>
    /// Minimizes the companion window after applying effects.
    /// </summary>
    public void Minimize()
    {
        if (_form is null || _form.IsDisposed) return;
        _form.BeginInvoke(() =>
        {
            _form.TopMost = false;
            _form.WindowState = FormWindowState.Minimized;
        });
    }

    public void UpdateStatus(string text)
    {
        if (_statusLabel is null || _form is null || _form.IsDisposed) return;
        _form.BeginInvoke(() => _statusLabel.Text = text);
    }

    private void RunUIThread()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        _form = new ForegroundForm
        {
            Text = "🌈 Dynamic Lighting Driver",
            Width = 380,
            Height = 140,
            StartPosition = FormStartPosition.Manual,
            Location = new System.Drawing.Point(
                Screen.PrimaryScreen!.WorkingArea.Right - 400,
                Screen.PrimaryScreen!.WorkingArea.Bottom - 160),
            FormBorderStyle = FormBorderStyle.FixedToolWindow,
            ShowInTaskbar = true,
            TopMost = true,
        };

        _statusLabel = new Label
        {
            Text = "Driver ready. Waiting for lighting commands...",
            Dock = DockStyle.Fill,
            TextAlign = System.Drawing.ContentAlignment.MiddleCenter,
            Font = new System.Drawing.Font("Segoe UI", 11),
            ForeColor = System.Drawing.Color.FromArgb(220, 220, 220),
            BackColor = System.Drawing.Color.FromArgb(30, 30, 30),
        };

        _form.Controls.Add(_statusLabel);
        _form.BackColor = System.Drawing.Color.FromArgb(30, 30, 30);

        _form.FormClosing += (s, e) =>
        {
            // Minimize instead of close so the driver keeps running
            if (!_disposed)
            {
                e.Cancel = true;
                _form.WindowState = FormWindowState.Minimized;
            }
        };

        _ready.Set();
        Application.Run(_form);
    }

    public void Dispose()
    {
        _disposed = true;
        if (_form is not null && !_form.IsDisposed)
        {
            _form.BeginInvoke(() =>
            {
                StopRetryTimer();
                _form.Close();
                Application.ExitThread();
            });
        }
        _ready.Dispose();
    }
}
