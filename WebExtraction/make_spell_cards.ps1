# Makes the spell card backgrounds (spell-cantrip.png, spell-1.png ... spell-9.png) from common.png.
# Each level gets its own border color, a light tint of that color on the parchment, and a faint magic circle
# behind the description. Uses only what comes with Windows (.NET System.Drawing), so nothing needs installing.
#
#   powershell -ExecutionPolicy Bypass -File make_spell_cards.ps1
#
# To change a level's color, edit $levels below and run it again.

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$cardDir = Split-Path -Parent $PSScriptRoot     # the main CardHTML folder, next to common.png
$template = Join-Path $cardDir 'common.png'

# File name -> border color (hex). Cool colors for low levels, warmer and darker toward 9th.
$levels = [ordered]@{
    'spell-cantrip' = '#6B7B8C'   # slate
    'spell-1'       = '#2A9D8F'   # teal
    'spell-2'       = '#3E9B4F'   # green
    'spell-3'       = '#1E7FD8'   # blue
    'spell-4'       = '#3F4BB0'   # indigo
    'spell-5'       = '#7B2FA8'   # purple
    'spell-6'       = '#C2185B'   # magenta
    'spell-7'       = '#C62828'   # red
    'spell-8'       = '#E0620B'   # orange
    'spell-9'       = '#20203A'   # midnight
}

# Pixel work in C# (a PowerShell loop over 787,500 pixels would take minutes)
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public static class SpellCardPainter {
    // The template's outer border is flat gray (122,122,122), in a band about 25px wide around the edge.
    const int Band = 27, Gray = 122;

    public static void Recolor(Bitmap bmp, Color border, double tint) {
        var rect = new Rectangle(0, 0, bmp.Width, bmp.Height);
        var data = bmp.LockBits(rect, ImageLockMode.ReadWrite, PixelFormat.Format24bppRgb);
        int stride = data.Stride, w = bmp.Width, h = bmp.Height;
        var px = new byte[stride * h];
        Marshal.Copy(data.Scan0, px, 0, px.Length);

        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int i = y * stride + x * 3;
                int b = px[i], g = px[i + 1], r = px[i + 2];
                bool inBand = x < Band || y < Band || x >= w - Band || y >= h - Band;
                int max = Math.Max(r, Math.Max(g, b)), min = Math.Min(r, Math.Min(g, b));

                if (inBand && max - min < 14 && max <= 240) {
                    // Border gray, including its anti-aliased edge (gray blended toward white): keep the blend
                    double t = Math.Max(0, Math.Min(1, (max - Gray) / (255.0 - Gray)));
                    px[i + 2] = (byte)(border.R + (255 - border.R) * t);
                    px[i + 1] = (byte)(border.G + (255 - border.G) * t);
                    px[i]     = (byte)(border.B + (255 - border.B) * t);
                } else if (!inBand) {
                    // Parchment, frame lines and corners: a light wash of the level color
                    px[i + 2] = (byte)(r + (border.R - r) * tint);
                    px[i + 1] = (byte)(g + (border.G - g) * tint);
                    px[i]     = (byte)(b + (border.B - b) * tint);
                }
            }
        }
        Marshal.Copy(px, 0, data.Scan0, px.Length);
        bmp.UnlockBits(data);
    }

    // A faint magic circle centered in the description box: rings, an eight-pointed star and tick marks
    public static void DrawCircle(Bitmap bmp, Color color, int alpha) {
        using (var gfx = Graphics.FromImage(bmp)) {
            gfx.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            var c = Color.FromArgb(alpha, color);
            float cx = bmp.Width / 2f, cy = 605f;
            using (var thick = new Pen(c, 3f))
            using (var thin = new Pen(c, 1.5f)) {
                Ring(gfx, thick, cx, cy, 255);
                Ring(gfx, thin, cx, cy, 240);
                Ring(gfx, thin, cx, cy, 150);
                Ring(gfx, thin, cx, cy, 70);
                // Two squares make an eight-pointed star inside the inner ring
                for (int s = 0; s < 2; s++) {
                    var pts = new PointF[4];
                    for (int k = 0; k < 4; k++) {
                        double a = (k * 90 + s * 45 - 90) * Math.PI / 180;
                        pts[k] = new PointF(cx + (float)(240 * Math.Cos(a)), cy + (float)(240 * Math.Sin(a)));
                    }
                    gfx.DrawPolygon(thin, pts);
                }
                // Tick marks between the two outer rings, and small circles at the star's points
                for (int k = 0; k < 72; k++) {
                    double a = k * 5 * Math.PI / 180;
                    float r1 = k % 2 == 0 ? 240 : 246;
                    gfx.DrawLine(thin, cx + (float)(r1 * Math.Cos(a)), cy + (float)(r1 * Math.Sin(a)),
                                       cx + (float)(255 * Math.Cos(a)), cy + (float)(255 * Math.Sin(a)));
                }
                for (int k = 0; k < 8; k++) {
                    double a = (k * 45 - 90) * Math.PI / 180;
                    Ring(gfx, thin, cx + (float)(195 * Math.Cos(a)), cy + (float)(195 * Math.Sin(a)), 14);
                }
            }
        }
    }

    static void Ring(Graphics gfx, Pen pen, float cx, float cy, float r) {
        gfx.DrawEllipse(pen, cx - r, cy - r, r * 2, r * 2);
    }
}
'@

foreach ($name in $levels.Keys) {
    $color = [System.Drawing.ColorTranslator]::FromHtml($levels[$name])
    $bmp = New-Object System.Drawing.Bitmap $template
    $card = $bmp.Clone((New-Object System.Drawing.Rectangle 0, 0, $bmp.Width, $bmp.Height), [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $bmp.Dispose()
    [SpellCardPainter]::Recolor($card, $color, 0.06)
    [SpellCardPainter]::DrawCircle($card, $color, 34)
    $out = Join-Path $cardDir "$name.png"
    $card.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
    $card.Dispose()
    Write-Output "Created $out"
}
