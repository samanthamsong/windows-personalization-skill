using System.Drawing.Drawing2D;
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
    private Label? _effectLabel;
    private Label? _detailLabel;
    private Label? _titleLabel;
    private Panel? _accentBar;
    private Panel? _bottomPanel;
    private Panel? _titlePanel;
    private Label? _themeToggle;
    private Label? _hideToggle;
    private Label? _musicToggle;
    private NotifyIcon? _trayIcon;
    private Thread? _uiThread;
    private readonly ManualResetEventSlim _ready = new();
    private volatile bool _disposed;
    private bool _isLightMode;
    private System.Windows.Forms.Timer? _retryTimer;
    private int _retryCount;
    private volatile bool _holdForeground;

    // Spotify panel controls
    private Panel? _spotifyPanel;
    private Label? _spotifyTrackLabel;
    private Label? _spotifyArtistLabel;
    private Label? _spotifyMoodLabel;
    private Panel? _spotifyColorsPanel;
    private bool _spotifyPanelVisible;
    private bool _hasSpotifyData;
    private const int BASE_HEIGHT = 180;
    private const int SPOTIFY_PANEL_HEIGHT = 90;

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
        if (_form is null || _form.IsDisposed) return;
        _form.BeginInvoke(() =>
        {
            // Parse effect name from status text if present
            // Patterns: "🔴 Solid ...", "🎨 Custom ...", "🌈 pattern — ..."
            string effectName = "";
            string detail = text;

            if (text.Contains("—"))
            {
                var parts = text.Split('—', 2);
                effectName = parts[0].Trim();
                detail = parts[1].Trim();
            }
            else if (text.StartsWith("🔴") || text.StartsWith("🎨") || text.StartsWith("🌈"))
            {
                effectName = text;
                detail = "";
            }

            if (_effectLabel is not null)
            {
                _effectLabel.Text = effectName != "" ? effectName : text;
            }
            if (_detailLabel is not null)
            {
                _detailLabel.Text = detail;
                _detailLabel.Visible = detail != "";
            }
            if (_statusLabel is not null)
            {
                _statusLabel.Text = text;
            }
        });
    }

    /// <summary>
    /// Switches the companion window between light and dark themes.
    /// </summary>
    public void SetTheme(bool light)
    {
        if (_form is null || _form.IsDisposed) return;
        _form.BeginInvoke(() =>
        {
            _isLightMode = light;

            var bgColor = light
                ? System.Drawing.Color.FromArgb(245, 245, 248)
                : System.Drawing.Color.FromArgb(24, 24, 28);
            var textPrimary = light
                ? System.Drawing.Color.FromArgb(30, 30, 35)
                : System.Drawing.Color.FromArgb(240, 240, 245);
            var textSecondary = light
                ? System.Drawing.Color.FromArgb(90, 90, 100)
                : System.Drawing.Color.FromArgb(160, 160, 170);
            var textDim = light
                ? System.Drawing.Color.FromArgb(130, 130, 140)
                : System.Drawing.Color.FromArgb(100, 100, 110);
            var statusGreen = System.Drawing.Color.FromArgb(80, 200, 120);

            _form.BackColor = bgColor;
            if (_accentBar is not null) _accentBar.BackColor = System.Drawing.Color.FromArgb(120, 90, 220);
            if (_titleLabel is not null) { _titleLabel.ForeColor = textDim; _titleLabel.BackColor = bgColor; }
            if (_titlePanel is not null) _titlePanel.BackColor = bgColor;
            if (_effectLabel is not null) { _effectLabel.ForeColor = textPrimary; _effectLabel.BackColor = bgColor; }
            if (_detailLabel is not null) { _detailLabel.ForeColor = textSecondary; _detailLabel.BackColor = bgColor; }
            if (_bottomPanel is not null) _bottomPanel.BackColor = bgColor;
            if (_statusLabel is not null) { _statusLabel.ForeColor = statusGreen; _statusLabel.BackColor = bgColor; }
            if (_themeToggle is not null)
            {
                _themeToggle.Text = light ? "🌙" : "☀️";
                _themeToggle.ForeColor = textDim;
                _themeToggle.BackColor = bgColor;
            }
            if (_hideToggle is not null)
            {
                _hideToggle.ForeColor = textDim;
                _hideToggle.BackColor = bgColor;
            }
            if (_musicToggle is not null)
            {
                _musicToggle.ForeColor = _hasSpotifyData
                    ? System.Drawing.Color.FromArgb(30, 215, 96)
                    : textDim;
                _musicToggle.BackColor = bgColor;
            }
            ApplySpotifyPanelTheme(bgColor, textPrimary, textSecondary);

            // Catch any remaining child controls that weren't explicitly themed
            ApplyBackColorRecursive(_form, bgColor);
        });
    }

    /// <summary>
    /// Updates the Spotify "now playing" panel with track info.
    /// Called by the SET_SPOTIFY command when the Python sync script sends track data.
    /// </summary>
    public void SetSpotifyData(string track, string artist, string mood, string[] hexColors)
    {
        if (_form is null || _form.IsDisposed) return;
        _form.BeginInvoke(() =>
        {
            _hasSpotifyData = true;

            if (_spotifyTrackLabel is not null)
                _spotifyTrackLabel.Text = $"🎵 {track}";
            if (_spotifyArtistLabel is not null)
                _spotifyArtistLabel.Text = artist;
            if (_spotifyMoodLabel is not null)
                _spotifyMoodLabel.Text = mood.Length > 0 ? $"✦ {mood}" : "";

            // Update color swatches
            if (_spotifyColorsPanel is not null)
            {
                _spotifyColorsPanel.Controls.Clear();
                int swatchX = 0;
                foreach (var hex in hexColors)
                {
                    try
                    {
                        var c = System.Drawing.ColorTranslator.FromHtml(hex.StartsWith("#") ? hex : $"#{hex}");
                        var swatch = new Panel
                        {
                            Size = new System.Drawing.Size(18, 18),
                            Location = new System.Drawing.Point(swatchX, 0),
                            BackColor = c,
                        };
                        // Round the swatch
                        var swatchPath = new System.Drawing.Drawing2D.GraphicsPath();
                        swatchPath.AddEllipse(0, 0, 18, 18);
                        swatch.Region = new System.Drawing.Region(swatchPath);
                        _spotifyColorsPanel.Controls.Add(swatch);
                        swatchX += 24;
                    }
                    catch { /* skip bad hex */ }
                }
            }

            // Light up the music toggle
            if (_musicToggle is not null)
                _musicToggle.ForeColor = System.Drawing.Color.FromArgb(30, 215, 96); // Spotify green

            // Auto-show the panel if it was hidden
            if (!_spotifyPanelVisible)
                ToggleSpotifyPanel();
        });
    }

    /// <summary>
    /// Hides the Spotify panel and clears track data.
    /// Called by the CLEAR_SPOTIFY command when sync stops.
    /// </summary>
    public void ClearSpotifyData()
    {
        if (_form is null || _form.IsDisposed) return;
        _form.BeginInvoke(() =>
        {
            _hasSpotifyData = false;

            if (_spotifyTrackLabel is not null) _spotifyTrackLabel.Text = "";
            if (_spotifyArtistLabel is not null) _spotifyArtistLabel.Text = "";
            if (_spotifyMoodLabel is not null) _spotifyMoodLabel.Text = "";
            if (_spotifyColorsPanel is not null) _spotifyColorsPanel.Controls.Clear();

            // Dim the music toggle
            var textDim = _isLightMode
                ? System.Drawing.Color.FromArgb(130, 130, 140)
                : System.Drawing.Color.FromArgb(100, 100, 110);
            if (_musicToggle is not null) _musicToggle.ForeColor = textDim;

            // Hide the panel
            if (_spotifyPanelVisible)
                ToggleSpotifyPanel();
        });
    }

    private void ToggleSpotifyPanel()
    {
        if (_form is null || _form.IsDisposed || _spotifyPanel is null) return;

        _spotifyPanelVisible = !_spotifyPanelVisible;
        _spotifyPanel.Visible = _spotifyPanelVisible;

        var newHeight = _spotifyPanelVisible ? BASE_HEIGHT + SPOTIFY_PANEL_HEIGHT : BASE_HEIGHT;
        _form.Height = newHeight;

        // Rebuild rounded corners for new height
        var radius = 16;
        var path = new System.Drawing.Drawing2D.GraphicsPath();
        path.AddArc(0, 0, radius, radius, 180, 90);
        path.AddArc(_form.Width - radius, 0, radius, radius, 270, 90);
        path.AddArc(_form.Width - radius, newHeight - radius, radius, radius, 0, 90);
        path.AddArc(0, newHeight - radius, radius, radius, 90, 90);
        path.CloseFigure();
        _form.Region = new System.Drawing.Region(path);
    }

    private void ApplySpotifyPanelTheme(System.Drawing.Color bg, System.Drawing.Color textPrimary, System.Drawing.Color textSecondary)
    {
        if (_spotifyPanel is not null) _spotifyPanel.BackColor = bg;
        if (_spotifyTrackLabel is not null)
        {
            _spotifyTrackLabel.ForeColor = textPrimary;
            _spotifyTrackLabel.BackColor = bg;
        }
        if (_spotifyArtistLabel is not null)
        {
            _spotifyArtistLabel.ForeColor = textSecondary;
            _spotifyArtistLabel.BackColor = bg;
        }
        if (_spotifyMoodLabel is not null)
        {
            _spotifyMoodLabel.ForeColor = System.Drawing.Color.FromArgb(30, 215, 96);
            _spotifyMoodLabel.BackColor = bg;
        }
        if (_spotifyColorsPanel is not null)
        {
            _spotifyColorsPanel.BackColor = bg;
        }
    }

    /// <summary>
    /// Recursively sets BackColor on all child panels/labels that still have
    /// a dark or light background from the previous theme. Skips the accent bar
    /// and color swatch circles (which have intentional custom colors).
    /// </summary>
    private static void ApplyBackColorRecursive(Control parent, System.Drawing.Color bg)
    {
        foreach (Control child in parent.Controls)
        {
            // Skip controls with intentional custom colors
            if (child.Tag is "keep-color") continue;
            // Skip color swatch circles (small 18×18 panels with non-standard bg)
            if (child is Panel p && p.Width == 18 && p.Height == 18) continue;

            // Only update panels and labels (not the accent bar which is 3px tall at top)
            if (child is Panel panel && panel.Height > 3)
            {
                panel.BackColor = bg;
            }
            else if (child is Label label)
            {
                label.BackColor = bg;
            }

            if (child.HasChildren)
                ApplyBackColorRecursive(child, bg);
        }
    }

    private static System.Drawing.Icon CreatePaletteIcon()
    {
        // Draw a 16×16 artist palette icon for the system tray
        var bmp = new System.Drawing.Bitmap(16, 16);
        using (var g = System.Drawing.Graphics.FromImage(bmp))
        {
            g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            g.Clear(System.Drawing.Color.Transparent);

            // Palette body — oval shape
            using var paletteBrush = new System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(230, 220, 200));
            using var outlinePen = new System.Drawing.Pen(System.Drawing.Color.FromArgb(80, 70, 60), 1.2f);
            g.FillEllipse(paletteBrush, 1, 2, 14, 12);
            g.DrawEllipse(outlinePen, 1, 2, 14, 12);

            // Thumb hole
            using var holeBrush = new System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(60, 55, 50));
            g.FillEllipse(holeBrush, 3, 8, 3, 3);

            // Color dots
            using var red = new System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(220, 60, 60));
            using var blue = new System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(60, 100, 240));
            using var green = new System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(60, 200, 80));
            using var yellow = new System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(240, 200, 40));
            using var purple = new System.Drawing.SolidBrush(System.Drawing.Color.FromArgb(160, 60, 220));

            g.FillEllipse(red, 5, 3, 3, 3);
            g.FillEllipse(blue, 9, 3, 3, 3);
            g.FillEllipse(green, 11, 6, 3, 3);
            g.FillEllipse(yellow, 8, 9, 3, 3);
            g.FillEllipse(purple, 4, 7, 2.5f, 2.5f);
        }

        var handle = bmp.GetHicon();
        return System.Drawing.Icon.FromHandle(handle);
    }

    private void RunUIThread()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);

        var bgColor = System.Drawing.Color.FromArgb(24, 24, 28);
        var surfaceColor = System.Drawing.Color.FromArgb(32, 32, 38);
        var textPrimary = System.Drawing.Color.FromArgb(240, 240, 245);
        var textSecondary = System.Drawing.Color.FromArgb(160, 160, 170);
        var textDim = System.Drawing.Color.FromArgb(100, 100, 110);
        var accentColor = System.Drawing.Color.FromArgb(120, 90, 220);

        _form = new ForegroundForm
        {
            Text = "Dynamic Lighting",
            Width = 360,
            Height = 180,
            StartPosition = FormStartPosition.Manual,
            Location = new System.Drawing.Point(
                Screen.PrimaryScreen!.WorkingArea.Right - 380,
                Screen.PrimaryScreen!.WorkingArea.Bottom - 200),
            FormBorderStyle = FormBorderStyle.None,
            ShowInTaskbar = true,
            TopMost = true,
            BackColor = bgColor,
            Padding = new Padding(0),
        };

        // Rounded corners via Region
        var radius = 16;
        var path = new System.Drawing.Drawing2D.GraphicsPath();
        path.AddArc(0, 0, radius, radius, 180, 90);
        path.AddArc(_form.Width - radius, 0, radius, radius, 270, 90);
        path.AddArc(_form.Width - radius, _form.Height - radius, radius, radius, 0, 90);
        path.AddArc(0, _form.Height - radius, radius, radius, 90, 90);
        path.CloseFigure();
        _form.Region = new System.Drawing.Region(path);

        // Top accent bar — thin colored line
        _accentBar = new Panel
        {
            Height = 3,
            Dock = DockStyle.Top,
            BackColor = accentColor,
        };

        // Title row with theme toggle
        _titlePanel = new Panel
        {
            Height = 28,
            Dock = DockStyle.Top,
            BackColor = bgColor,
        };

        _titleLabel = new Label
        {
            Text = "⚡ Dynamic Lighting",
            AutoSize = false,
            Height = 28,
            Dock = DockStyle.Left,
            Width = 240,
            TextAlign = System.Drawing.ContentAlignment.MiddleLeft,
            Font = new System.Drawing.Font("Segoe UI", 9f, System.Drawing.FontStyle.Regular),
            ForeColor = textDim,
            BackColor = bgColor,
            Padding = new Padding(16, 4, 0, 0),
        };

        _themeToggle = new Label
        {
            Text = "☀️",
            AutoSize = false,
            Height = 28,
            Width = 36,
            Dock = DockStyle.Right,
            TextAlign = System.Drawing.ContentAlignment.MiddleCenter,
            Font = new System.Drawing.Font("Segoe UI", 12f),
            ForeColor = textDim,
            BackColor = bgColor,
            Cursor = Cursors.Hand,
        };
        _themeToggle.Click += (s, e) => SetTheme(!_isLightMode);

        _hideToggle = new Label
        {
            Text = "👁",
            AutoSize = false,
            Height = 28,
            Width = 36,
            Dock = DockStyle.Right,
            TextAlign = System.Drawing.ContentAlignment.MiddleCenter,
            Font = new System.Drawing.Font("Segoe UI", 12f),
            ForeColor = textDim,
            BackColor = bgColor,
            Cursor = Cursors.Hand,
        };
        _hideToggle.Click += (s, e) =>
        {
            _form!.Opacity = 0;
            _form.ShowInTaskbar = false;
        };

        _musicToggle = new Label
        {
            Text = "🎵",
            AutoSize = false,
            Height = 28,
            Width = 36,
            Dock = DockStyle.Right,
            TextAlign = System.Drawing.ContentAlignment.MiddleCenter,
            Font = new System.Drawing.Font("Segoe UI", 12f),
            ForeColor = textDim,
            BackColor = bgColor,
            Cursor = Cursors.Hand,
        };
        _musicToggle.Click += (s, e) =>
        {
            if (_hasSpotifyData)
                ToggleSpotifyPanel();
        };

        _titlePanel.Controls.Add(_titleLabel);
        _titlePanel.Controls.Add(_hideToggle);
        _titlePanel.Controls.Add(_musicToggle);
        _titlePanel.Controls.Add(_themeToggle);

        // Effect name — large and prominent
        _effectLabel = new Label
        {
            Text = "Ready",
            AutoSize = false,
            Height = 48,
            Dock = DockStyle.Top,
            TextAlign = System.Drawing.ContentAlignment.MiddleLeft,
            Font = new System.Drawing.Font("Segoe UI Semibold", 14f, System.Drawing.FontStyle.Bold),
            ForeColor = textPrimary,
            BackColor = bgColor,
            Padding = new Padding(16, 0, 8, 0),
            AutoEllipsis = true,
        };

        // Detail / subtitle
        _detailLabel = new Label
        {
            Text = "Waiting for lighting commands...",
            AutoSize = false,
            Height = 24,
            Dock = DockStyle.Top,
            TextAlign = System.Drawing.ContentAlignment.MiddleLeft,
            Font = new System.Drawing.Font("Segoe UI", 9f),
            ForeColor = textSecondary,
            BackColor = bgColor,
            Padding = new Padding(16, 0, 8, 0),
            AutoEllipsis = true,
        };

        // Bottom bar with status dot
        _bottomPanel = new Panel
        {
            Height = 32,
            Dock = DockStyle.Top,
            BackColor = bgColor,
            Padding = new Padding(16, 8, 16, 0),
        };

        _statusLabel = new Label
        {
            Text = "● Connected",
            AutoSize = true,
            Font = new System.Drawing.Font("Segoe UI", 8.5f),
            ForeColor = System.Drawing.Color.FromArgb(80, 200, 120),
            BackColor = bgColor,
            Location = new System.Drawing.Point(16, 8),
        };
        _bottomPanel.Controls.Add(_statusLabel);

        // Spotify "now playing" panel — hidden by default, shown via music toggle
        _spotifyPanel = new Panel
        {
            Height = SPOTIFY_PANEL_HEIGHT,
            Dock = DockStyle.Top,
            BackColor = bgColor,
            Visible = false,
            Padding = new Padding(16, 4, 16, 4),
        };

        // Thin separator line at top of Spotify panel
        var spotifySep = new Panel
        {
            Height = 1,
            Dock = DockStyle.Top,
            BackColor = System.Drawing.Color.FromArgb(50, 50, 58),
        };

        _spotifyTrackLabel = new Label
        {
            Text = "",
            AutoSize = false,
            Height = 24,
            Dock = DockStyle.Top,
            TextAlign = System.Drawing.ContentAlignment.MiddleLeft,
            Font = new System.Drawing.Font("Segoe UI Semibold", 9.5f, System.Drawing.FontStyle.Bold),
            ForeColor = textPrimary,
            BackColor = bgColor,
            Padding = new Padding(0, 4, 8, 0),
            AutoEllipsis = true,
        };

        _spotifyArtistLabel = new Label
        {
            Text = "",
            AutoSize = false,
            Height = 20,
            Dock = DockStyle.Top,
            TextAlign = System.Drawing.ContentAlignment.MiddleLeft,
            Font = new System.Drawing.Font("Segoe UI", 8.5f),
            ForeColor = textSecondary,
            BackColor = bgColor,
            AutoEllipsis = true,
        };

        var spotifyBottomRow = new Panel
        {
            Height = 28,
            Dock = DockStyle.Top,
            BackColor = bgColor,
        };

        _spotifyMoodLabel = new Label
        {
            Text = "",
            AutoSize = true,
            Font = new System.Drawing.Font("Segoe UI", 8.5f),
            ForeColor = System.Drawing.Color.FromArgb(30, 215, 96),
            BackColor = bgColor,
            Location = new System.Drawing.Point(0, 4),
        };

        _spotifyColorsPanel = new Panel
        {
            Height = 20,
            Width = 150,
            Location = new System.Drawing.Point(180, 2),
            BackColor = bgColor,
        };

        spotifyBottomRow.Controls.Add(_spotifyMoodLabel);
        spotifyBottomRow.Controls.Add(_spotifyColorsPanel);

        // Add to Spotify panel in reverse dock order
        _spotifyPanel.Controls.Add(spotifyBottomRow);
        _spotifyPanel.Controls.Add(_spotifyArtistLabel);
        _spotifyPanel.Controls.Add(_spotifyTrackLabel);
        _spotifyPanel.Controls.Add(spotifySep);

        // Hidden status label for backwards compatibility (UpdateStatus still sets it)
        // The visible UI is driven by _effectLabel and _detailLabel

        // Add controls in reverse dock order (top = last added docks first)
        _form.Controls.Add(_spotifyPanel);
        _form.Controls.Add(_bottomPanel);
        _form.Controls.Add(_detailLabel);
        _form.Controls.Add(_effectLabel);
        _form.Controls.Add(_titlePanel);
        _form.Controls.Add(_accentBar);

        // Draggable window (since FormBorderStyle.None)
        bool dragging = false;
        System.Drawing.Point dragOffset = default;
        foreach (Control ctrl in _form.Controls)
        {
            ctrl.MouseDown += (s, e) =>
            {
                if (e.Button == MouseButtons.Left) { dragging = true; dragOffset = e.Location; }
            };
            ctrl.MouseMove += (s, e) =>
            {
                if (dragging)
                    _form.Location = new System.Drawing.Point(
                        _form.Location.X + e.X - dragOffset.X,
                        _form.Location.Y + e.Y - dragOffset.Y);
            };
            ctrl.MouseUp += (s, e) => { dragging = false; };
        }

        // System tray icon (always visible for discoverability)
        _trayIcon = new NotifyIcon
        {
            Text = "Dynamic Lighting",
            Icon = CreatePaletteIcon(),
            Visible = true,
        };
        _trayIcon.Click += (s, e) =>
        {
            _form!.Opacity = 1;
            _form.ShowInTaskbar = true;
        };

        _form.FormClosing += (s, e) =>
        {
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
                if (_trayIcon is not null)
                {
                    _trayIcon.Visible = false;
                    _trayIcon.Dispose();
                }
                _form.Close();
                Application.ExitThread();
            });
        }
        _ready.Dispose();
    }
}
