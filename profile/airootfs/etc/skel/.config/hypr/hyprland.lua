-- ---------------------------------------------------------------------------
-- FlyArchOs — конфигурация Hyprland (Lua; Hyprland 0.57+ не читает .conf)
-- Документация: https://wiki.hypr.land/configuring/
-- ---------------------------------------------------------------------------

local mainMod = "SUPER"
local terminal = "kitty"
local menu = "wofi --show drun"
local browser = "firefox"
local files = "thunar"
local wallpaper = "/usr/share/backgrounds/flyarchos/default.jpg"

-------------------------------
---- MONITORS / AUTOSTART ----
-------------------------------

hl.monitor({
    output = "",
    mode = "preferred",
    position = "auto",
    scale = "auto",
})

hl.on("hyprland.start", function()
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP")
    hl.exec_cmd("systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP")
    hl.exec_cmd("awww-daemon")
    -- awww img сразу после старта демона может не успеть к сокету.
    hl.exec_cmd("sh -c 'sleep 0.5; awww img " .. wallpaper .. " --transition-type wipe'")
    hl.exec_cmd("waybar")
    hl.exec_cmd("mako")
    hl.exec_cmd("hypridle")
    hl.exec_cmd("wl-paste --type text --watch cliphist store")
    hl.exec_cmd("wl-paste --type image --watch cliphist store")
    hl.exec_cmd("nm-applet --indicator")
    hl.exec_cmd("blueman-applet")
    hl.exec_cmd("/usr/lib/polkit-kde-authentication-agent-1")
    hl.exec_cmd("flyarchos-welcome --autostart")
end)

----------------------
---- LOOK & INPUT ----
----------------------

hl.config({
    general = {
        gaps_in = 4,
        gaps_out = 8,
        border_size = 2,
        col = {
            active_border = { colors = { "rgba(22d3eeff)", "rgba(f0559bff)" }, angle = 45 },
            inactive_border = "rgba(24242faa)",
        },
        layout = "dwindle",
        resize_on_border = true,
        allow_tearing = false,
    },

    decoration = {
        rounding = 12,
        active_opacity = 1.0,
        inactive_opacity = 0.94,
        blur = {
            enabled = true,
            size = 6,
            passes = 2,
            new_optimizations = true,
            ignore_opacity = true,
        },
        shadow = {
            enabled = true,
            range = 14,
            render_power = 3,
            color = "rgba(08080faa)",
        },
    },

    animations = {
        enabled = true,
    },

    input = {
        kb_layout = "us,ru",
        kb_variant = "",
        kb_options = "grp:alt_shift_toggle,compose:ralt",
        kb_model = "",
        kb_rules = "",
        repeat_rate = 35,
        repeat_delay = 300,
        follow_mouse = 1,
        sensitivity = 0,
        touchpad = {
            natural_scroll = true,
            disable_while_typing = true,
            tap_to_click = true,
            drag_lock = 1,
        },
    },

    dwindle = {
        preserve_split = true,
    },

    master = {
        new_status = "master",
        new_on_top = true,
    },

    misc = {
        disable_hyprland_logo = false,
        disable_splash_rendering = true,
        mouse_move_enables_dpms = true,
        key_press_enables_dpms = true,
    },
})

hl.curve("fly", { type = "bezier", points = { { 0.05, 0.9 }, { 0.1, 1.05 } } })
hl.animation({ leaf = "windows", enabled = true, speed = 6, bezier = "fly", style = "slide" })
hl.animation({ leaf = "windowsIn", enabled = true, speed = 5, bezier = "fly", style = "popin 80%" })
hl.animation({ leaf = "windowsOut", enabled = true, speed = 4, bezier = "fly", style = "popin 80%" })
hl.animation({ leaf = "border", enabled = true, speed = 10, bezier = "fly" })
hl.animation({ leaf = "fade", enabled = true, speed = 6, bezier = "fly" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 5, bezier = "fly", style = "slidevert" })

hl.gesture({
    fingers = 3,
    direction = "horizontal",
    action = "workspace",
})

------------------------
---- WINDOW RULES ------
------------------------

hl.window_rule({ name = "fly-float-pavucontrol", match = { class = "^(pavucontrol)$" }, float = true, center = true })
hl.window_rule({ name = "fly-float-blueman", match = { class = "^(blueman-manager)$" }, float = true, center = true })
hl.window_rule({ name = "fly-float-nm-editor", match = { class = "^(nm-connection-editor)$" }, float = true })
hl.window_rule({
    name = "fly-float-file-dialogs",
    match = { title = "^(Открыть файл|Open File|Save As|Save a File)$" },
    float = true,
})
hl.window_rule({ name = "fly-float-kcalc", match = { class = "^(org.kde.kcalc)$" }, float = true })
hl.window_rule({
    name = "fly-terminal-opacity",
    match = { class = "^(kitty|foot|org.kde.konsole)$" },
    opacity = "0.96 0.92",
})
hl.window_rule({ name = "fly-wofi-no-blur", match = { class = "^(wofi)$" }, no_blur = true })
hl.window_rule({
    name = "fly-suppress-maximize",
    match = { class = ".*" },
    suppress_event = "maximize",
})

----------------------
---- KEYBINDINGS -----
----------------------

-- Приложения
hl.bind(mainMod .. " + Return", hl.dsp.exec_cmd(terminal))
hl.bind(mainMod .. " + D", hl.dsp.exec_cmd(menu))
hl.bind(mainMod .. " + B", hl.dsp.exec_cmd(browser))
hl.bind(mainMod .. " + E", hl.dsp.exec_cmd(files))
hl.bind(mainMod .. " + T", hl.dsp.exec_cmd("kitty --hold flyarchos-info"))
hl.bind(mainMod .. " + L", hl.dsp.exec_cmd("hyprlock"))
hl.bind(mainMod .. " + W", hl.dsp.exec_cmd("flyarchos-wallpaper random"))
hl.bind(mainMod .. " + SHIFT + W", hl.dsp.exec_cmd("flyarchos-theme next"))
hl.bind(mainMod .. " + slash", hl.dsp.exec_cmd("kitty --hold flyarchos-info --keys"))
hl.bind(mainMod .. " + P", hl.dsp.exec_cmd([[grim -g "$(slurp)" - | wl-copy -t image/png]]))
hl.bind(mainMod .. " + SHIFT + P", hl.dsp.exec_cmd([[sh -c 'mkdir -p "$HOME/Pictures/Screenshots"; grim -g "$(slurp)" "$HOME/Pictures/Screenshots/shot-$(date +%Y%m%d-%H%M%S).png" && notify-send "Скриншот" "Сохранён в ~/Pictures/Screenshots"']]))
hl.bind(mainMod .. " + SHIFT + V", hl.dsp.exec_cmd([[cliphist list | wofi --dmenu --prompt "Буфер:" | cliphist decode | wl-copy]]))
hl.bind(mainMod .. " + N", hl.dsp.exec_cmd("pkill hyprsunset || hyprsunset -t 4200"))

-- Окна
hl.bind(mainMod .. " + Q", hl.dsp.window.close())
hl.bind(mainMod .. " + SHIFT + Q", hl.dsp.exit())
hl.bind(mainMod .. " + V", hl.dsp.window.float({ action = "toggle" }))
hl.bind(mainMod .. " + F", hl.dsp.window.fullscreen({ mode = "fullscreen", action = "toggle" }))
hl.bind(mainMod .. " + S", hl.dsp.layout("togglesplit")) -- dwindle
hl.bind(mainMod .. " + J", hl.dsp.window.cycle_next())
hl.bind(mainMod .. " + G", hl.dsp.group.toggle())
hl.bind(mainMod .. " + Tab", hl.dsp.group.next())
hl.bind(mainMod .. " + mouse_down", hl.dsp.focus({ workspace = "e+1" }))
hl.bind(mainMod .. " + mouse_up", hl.dsp.focus({ workspace = "e-1" }))

-- Фокус и рабочие столы
hl.bind(mainMod .. " + left", hl.dsp.focus({ direction = "left" }))
hl.bind(mainMod .. " + right", hl.dsp.focus({ direction = "right" }))
hl.bind(mainMod .. " + up", hl.dsp.focus({ direction = "up" }))
hl.bind(mainMod .. " + down", hl.dsp.focus({ direction = "down" }))

for i = 1, 10 do
    local key = i % 10 -- 10-й рабочий стол на клавише 0
    hl.bind(mainMod .. " + " .. key, hl.dsp.focus({ workspace = i }))
    hl.bind(mainMod .. " + SHIFT + " .. key, hl.dsp.window.move({ workspace = i }))
end

hl.bind(mainMod .. " + bracketright", hl.dsp.focus({ workspace = "e+1" }))
hl.bind(mainMod .. " + bracketleft", hl.dsp.focus({ workspace = "e-1" }))

-- Скриншоты
hl.bind("Print", hl.dsp.exec_cmd([[grim - | wl-copy -t image/png && notify-send "Скриншот" "Скопирован в буфер обмена"]]))
hl.bind(mainMod .. " + Print", hl.dsp.exec_cmd([[grim -g "$(slurp)" - | wl-copy -t image/png && notify-send "Скриншот" "Область скопирована"]]))

-- Звук, яркость, плеер (wpctl входит в wireplumber; pamixer в образе нет)
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"), { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), { locked = true, repeating = true })
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true, repeating = true })
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), { locked = true, repeating = true })
hl.bind("XF86AudioPlay", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioNext", hl.dsp.exec_cmd("playerctl next"), { locked = true })
hl.bind("XF86AudioPrev", hl.dsp.exec_cmd("playerctl previous"), { locked = true })
hl.bind("XF86MonBrightnessUp", hl.dsp.exec_cmd("brightnessctl set +5%"), { locked = true, repeating = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("brightnessctl set 5%-"), { locked = true, repeating = true })

-- Перемещение/размер плавающих окон мышью
hl.bind(mainMod .. " + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind(mainMod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })
hl.bind(mainMod .. " + ALT + mouse:272", hl.dsp.window.resize(), { mouse = true })

-- Тема оформления (flyarchos-theme) перекрывает цвета рамок выше.
require("theme")
