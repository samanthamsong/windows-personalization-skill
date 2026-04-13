using System.Globalization;
using System.Text.RegularExpressions;
using Windows.UI;

namespace DynamicLightingMcp;

public static class ColorParser
{
    private static readonly Regex HexColorRegex = new("#?[0-9a-fA-F]{6}", RegexOptions.Compiled);
    private static readonly Regex RgbRegex = new(@"rgb\s*\(\s*(?<r>\d{1,3})\s*,\s*(?<g>\d{1,3})\s*,\s*(?<b>\d{1,3})\s*\)", RegexOptions.Compiled | RegexOptions.IgnoreCase);
    private static readonly Color White = Color.FromArgb(255, 255, 255, 255);

    private static readonly Dictionary<string, Color> NamedColors = new(StringComparer.OrdinalIgnoreCase)
    {
        ["red"] = Color.FromArgb(255, 244, 67, 54),
        ["blue"] = Color.FromArgb(255, 33, 150, 243),
        ["green"] = Color.FromArgb(255, 76, 175, 80),
        ["teal"] = Color.FromArgb(255, 0, 150, 136),
        ["purple"] = Color.FromArgb(255, 156, 39, 176),
        ["orange"] = Color.FromArgb(255, 255, 152, 0),
        ["yellow"] = Color.FromArgb(255, 255, 235, 59),
        ["white"] = Color.FromArgb(255, 255, 255, 255),
        ["pink"] = Color.FromArgb(255, 233, 30, 99),
        ["cyan"] = Color.FromArgb(255, 0, 188, 212),
        ["gold"] = Color.FromArgb(255, 255, 193, 7),
        ["navy"] = Color.FromArgb(255, 13, 28, 82),
        ["coral"] = Color.FromArgb(255, 255, 127, 80),
        ["lavender"] = Color.FromArgb(255, 181, 126, 220),
        ["ivory"] = Color.FromArgb(255, 255, 255, 240),
        ["ocean"] = Color.FromArgb(255, 0, 131, 143),
        ["sunset"] = Color.FromArgb(255, 255, 94, 77),
        ["forest"] = Color.FromArgb(255, 46, 125, 50),
        ["midnight"] = Color.FromArgb(255, 25, 25, 112),
        ["cherry"] = Color.FromArgb(255, 193, 39, 45),
        ["amber"] = Color.FromArgb(255, 255, 191, 0),
        ["mint"] = Color.FromArgb(255, 152, 255, 152),
        ["peach"] = Color.FromArgb(255, 255, 203, 164),
        ["rose"] = Color.FromArgb(255, 255, 102, 204),
        ["magenta"] = Color.FromArgb(255, 255, 0, 255),
        ["turquoise"] = Color.FromArgb(255, 64, 224, 208),
        ["sky"] = Color.FromArgb(255, 135, 206, 235),
        ["aqua"] = Color.FromArgb(255, 0, 255, 255),
        ["violet"] = Color.FromArgb(255, 143, 0, 255),
        ["lime"] = Color.FromArgb(255, 205, 220, 57),
        ["indigo"] = Color.FromArgb(255, 63, 81, 181),
        ["crimson"] = Color.FromArgb(255, 220, 20, 60),
        ["slate"] = Color.FromArgb(255, 96, 125, 139),
        ["sand"] = Color.FromArgb(255, 244, 164, 96),
        ["ice"] = Color.FromArgb(255, 224, 247, 250),
        ["charcoal"] = Color.FromArgb(255, 54, 69, 79),
        ["plum"] = Color.FromArgb(255, 142, 69, 133),
        ["lilac"] = Color.FromArgb(255, 200, 162, 200),
    };

    public static Color Parse(string input)
    {
        if (string.IsNullOrWhiteSpace(input))
        {
            return White;
        }

        var trimmed = input.Trim();

        if (NamedColors.TryGetValue(trimmed, out var named))
        {
            return named;
        }

        var rgbMatch = RgbRegex.Match(trimmed);
        if (rgbMatch.Success
            && byte.TryParse(rgbMatch.Groups["r"].Value, out var r)
            && byte.TryParse(rgbMatch.Groups["g"].Value, out var g)
            && byte.TryParse(rgbMatch.Groups["b"].Value, out var b))
        {
            return Color.FromArgb(255, r, g, b);
        }

        if (TryParseHex(trimmed, out var hexColor))
        {
            return hexColor;
        }

        return White;
    }

    public static (Color @base, Color accent) ParseEffectColors(string description)
    {
        if (string.IsNullOrWhiteSpace(description))
        {
            return (White, ShiftHue(White, 35));
        }

        var found = new List<Color>(2);
        var lowered = description.ToLowerInvariant();

        foreach (Match match in HexColorRegex.Matches(description))
        {
            if (TryParseHex(match.Value, out var hexColor))
            {
                found.Add(hexColor);
                if (found.Count == 2)
                {
                    return (found[0], found[1]);
                }
            }
        }

        foreach (var pair in NamedColors)
        {
            if (ContainsWord(lowered, pair.Key))
            {
                found.Add(pair.Value);
                if (found.Count == 2)
                {
                    return (found[0], found[1]);
                }
            }
        }

        foreach (Match match in RgbRegex.Matches(description))
        {
            var parsed = Parse(match.Value);
            found.Add(parsed);
            if (found.Count == 2)
            {
                return (found[0], found[1]);
            }
        }

        if (found.Count == 1)
        {
            return (found[0], ShiftHue(found[0], 35));
        }

        return GetKeywordDefaultColors(lowered);
    }

    private static bool TryParseHex(string input, out Color color)
    {
        color = White;

        var hex = input.Trim();
        if (hex.StartsWith("#", StringComparison.Ordinal))
        {
            hex = hex[1..];
        }

        if (hex.Length != 6)
        {
            return false;
        }

        if (!int.TryParse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var value))
        {
            return false;
        }

        var r = (byte)((value >> 16) & 0xFF);
        var g = (byte)((value >> 8) & 0xFF);
        var b = (byte)(value & 0xFF);
        color = Color.FromArgb(255, r, g, b);
        return true;
    }

    private static bool ContainsWord(string text, string word)
    {
        return Regex.IsMatch(text, $"\\b{Regex.Escape(word)}\\b", RegexOptions.IgnoreCase);
    }

    private static (Color @base, Color accent) GetKeywordDefaultColors(string loweredDescription)
    {
        if (ContainsAny(loweredDescription, "ocean", "sea", "water"))
        {
            return (NamedColors["teal"], NamedColors["white"]);
        }

        if (ContainsAny(loweredDescription, "fire", "lava", "ember"))
        {
            return (NamedColors["red"], NamedColors["orange"]);
        }

        if (ContainsAny(loweredDescription, "night", "starry", "stars"))
        {
            return (NamedColors["navy"], NamedColors["gold"]);
        }

        if (ContainsAny(loweredDescription, "forest", "nature"))
        {
            return (NamedColors["forest"], NamedColors["mint"]);
        }

        return (White, NamedColors["lavender"]);
    }

    private static bool ContainsAny(string text, params string[] keywords)
    {
        return keywords.Any(k => text.Contains(k, StringComparison.Ordinal));
    }

    private static Color ShiftHue(Color color, double degrees)
    {
        ToHsv(color, out var h, out var s, out var v);
        h = (h + degrees) % 360.0;
        return FromHsv(h, Math.Clamp(s, 0.3, 1.0), Math.Clamp(v, 0.45, 1.0));
    }

    private static void ToHsv(Color color, out double h, out double s, out double v)
    {
        var r = color.R / 255.0;
        var g = color.G / 255.0;
        var b = color.B / 255.0;

        var max = Math.Max(r, Math.Max(g, b));
        var min = Math.Min(r, Math.Min(g, b));
        var delta = max - min;

        if (delta == 0)
        {
            h = 0;
        }
        else if (max == r)
        {
            h = 60 * (((g - b) / delta) % 6);
        }
        else if (max == g)
        {
            h = 60 * (((b - r) / delta) + 2);
        }
        else
        {
            h = 60 * (((r - g) / delta) + 4);
        }

        if (h < 0)
        {
            h += 360;
        }

        s = max == 0 ? 0 : delta / max;
        v = max;
    }

    private static Color FromHsv(double h, double s, double v)
    {
        var c = v * s;
        var x = c * (1 - Math.Abs(((h / 60) % 2) - 1));
        var m = v - c;

        var (r1, g1, b1) = h switch
        {
            < 60 => (c, x, 0d),
            < 120 => (x, c, 0d),
            < 180 => (0d, c, x),
            < 240 => (0d, x, c),
            < 300 => (x, 0d, c),
            _ => (c, 0d, x),
        };

        var r = (byte)Math.Clamp((int)Math.Round((r1 + m) * 255), 0, 255);
        var g = (byte)Math.Clamp((int)Math.Round((g1 + m) * 255), 0, 255);
        var b = (byte)Math.Clamp((int)Math.Round((b1 + m) * 255), 0, 255);
        return Color.FromArgb(255, r, g, b);
    }
}
