-- ---------------------------------------------------------------------------
-- FlyArchOs — конфигурация Hyprland (Lua; Hyprland 0.57+ не читает .conf)
-- Документация: https://wiki.hypr.land/configuring/
-- ---------------------------------------------------------------------------

local mainMod = "SUPER"
local menu = "wofi --show drun"
local browser = "firefox"
local files = "thunar"
local wallpaper = "/usr/share/backgrounds/flyarchos/default.jpg"

-- ---------------------------------------------------------------------------
-- Автоматический режим производительности для виртуальных машин.
-- VMSVGA/SVGA3D заметно тяжелее обычной видеокарты: blur, тени, анимации и
-- прозрачность на ней превращаются в рывки мыши и окон. Поэтому в ВМ эффекты
-- выключаются заранее, а на обычном железе остаётся полный внешний вид.
-- Ручной выбор хранит flyarchos-performance в
-- ~/.config/flyarchos/performance-mode (auto/on/off), Super+F1 переключает.
-- ---------------------------------------------------------------------------
local function read_prefix(path, max_bytes)
    if not io or not io.open then
        return ""
    end

    local ok, data = pcall(function()
        local file = io.open(path, "r")
        if not file then
            return ""
        end
        local content = file:read(max_bytes or 4096) or ""
        file:close()
        return content
    end)

    return ok and data or ""
end

local function text_contains(text, needle)
    return text:lower():find(needle, 1, true) ~= nil
end

local dmi_text = table.concat({
    read_prefix("/sys/class/dmi/id/product_name", 256),
    read_prefix("/sys/class/dmi/id/product_version", 256),
    read_prefix("/sys/class/dmi/id/sys_vendor", 256),
    read_prefix("/sys/class/dmi/id/board_name", 256),
    read_prefix("/sys/class/dmi/id/board_vendor", 256),
    read_prefix("/sys/class/dmi/id/bios_vendor", 256),
}, "\n")
local cpu_text = read_prefix("/proc/cpuinfo", 16384)

local is_virtualbox = text_contains(dmi_text, "virtualbox")
    or text_contains(dmi_text, "innotek")
local is_vmware = text_contains(dmi_text, "vmware")
local is_virtual_machine = is_virtualbox
    or is_vmware
    or text_contains(dmi_text, "qemu")
    or text_contains(dmi_text, "kvm")
    or text_contains(dmi_text, "virtual machine")
    or text_contains(dmi_text, "parallels")
    or text_contains(dmi_text, "xen")
    or text_contains(cpu_text, "hypervisor")

local function detect_performance_mode()
    local value = ""

    if os and os.getenv then
        value = os.getenv("FLYARCHOS_PERFORMANCE_MODE") or ""

        if value == "" then
            local config_home = os.getenv("XDG_CONFIG_HOME")
            if not config_home or config_home == "" then
                local home = os.getenv("HOME") or ""
                if home ~= "" then
                    config_home = home .. "/.config"
                end
            end

            if config_home and config_home ~= "" then
                value = read_prefix(config_home .. "/flyarchos/performance-mode", 64)
            end
        end
    end

    value = value:lower():match("[%w_%-]+") or "auto"
    if value == "on" or value == "1" or value == "true" or value == "yes" then
        return true
    end
    if value == "off" or value == "0" or value == "false" or value == "no" then
        return false
    end

    return is_virtual_machine
end

local performance_mode = detect_performance_mode()
local visual_effects = not performance_mode
local terminal = performance_mode and "kitty -o background_opacity=1" or "kitty"
local wallpaper_transition = performance_mode and "none" or "wipe"

-------------------------------
---- MONITORS / AUTOSTART ----
-------------------------------

hl.monitor({
    output = "",
    mode = "preferred",
    position = "auto",
    -- Дробное масштабирование в ВМ заставляет композитор пересчитывать кадр.
    scale = performance_mode and "1" or "auto",
})

hl.on("hyprland.start", function()
    -- На VirtualBox/VMware SVGA клиенты OpenGL стабильнее и предсказуемее
    -- рисуются через llvmpipe/SHM. Переменная ставится после инициализации
    -- самого Hyprland, поэтому композитор продолжает использовать SVGA3D,
    -- а программный GL получают только дочерние приложения.
    if performance_mode and (is_virtualbox or is_vmware) then
        hl.env("LIBGL_ALWAYS_SOFTWARE", "1")
    end

    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP")
    hl.exec_cmd("systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP")
    hl.exec_cmd("awww-daemon")
    -- В медленной ВМ фиксированные 0.5 с не гарантируют готовность сокета:
    -- повторяем установку обоев до 10 секунд, иначе остаётся чёрный фон.
    hl.exec_cmd("sh -c 'for i in $(seq 1 50); do awww img " .. wallpaper
        .. " --transition-type " .. wallpaper_transition
        .. " && exit 0; sleep 0.2; done'")
    hl.exec_cmd("waybar")
    hl.exec_cmd("mako")
    hl.exec_cmd("hypridle")
    hl.exec_cmd("wl-paste --type text --watch cliphist store")
    hl.exec_cmd("wl-paste --type image --watch cliphist store")
    hl.exec_cmd("nm-applet --indicator")
    if performance_mode then
        -- Не запускаем тяжёлый GTK-апплет там, где Bluetooth-адаптера нет.
        hl.exec_cmd([[sh -c 'for d in /sys/class/bluetooth/hci*; do [ -e "$d" ] && exec blueman-applet; done']])
    else
        hl.exec_cmd("blueman-applet")
    end
    hl.exec_cmd("/usr/lib/polkit-kde-authentication-agent-1")
    if is_virtualbox then
        hl.exec_cmd("sh -c 'command -v VBoxClient-all >/dev/null 2>&1 && VBoxClient-all'")
    end
    if performance_mode then
        -- Даём панели и обоям подняться раньше сравнительно тяжёлого PyQt-окна.
        hl.exec_cmd("sh -c 'sleep 2; exec flyarchos-welcome --autostart'")
    else
        hl.exec_cmd("flyarchos-welcome --autostart")
    end
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
        rounding = performance_mode and 0 or 12,
        active_opacity = 1.0,
        inactive_opacity = performance_mode and 1.0 or 0.94,
        blur = {
            enabled = visual_effects,
            size = 3,
            passes = 1,
            new_optimizations = true,
            ignore_opacity = true,
        },
        shadow = {
            enabled = visual_effects,
            range = 8,
            render_power = 3,
            color = "rgba(08080faa)",
        },
    },

    animations = {
        enabled = visual_effects,
    },

    render = {
        direct_scanout = 0,
        -- Планировщик специально предназначен слабому/виртуальному GPU.
        new_render_scheduling = performance_mode,
    },

    debug = {
        vfr = true,
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
        disable_hyprland_logo = performance_mode,
        disable_splash_rendering = true,
        vrr = 0,
        animate_manual_resizes = false,
        animate_mouse_windowdragging = false,
        render_unfocused_fps = performance_mode and 5 or 15,
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
if not performance_mode then
    hl.window_rule({
        name = "fly-terminal-opacity",
        match = { class = "^(kitty|foot|org.kde.konsole)$" },
        opacity = "0.96 0.92",
    })
end
hl.window_rule({ name = "fly-wofi-no-blur", match = { class = "^(wofi)$" }, no_blur = true })
hl.window_rule({
    name = "fly-suppress-maximize",
    match = { class = ".*" },
    suppress_event = "maximize",
})

----------------------
---- KEYBINDINGS -----
----------------------

-- Производительность: авто/вкл/выкл для Hyprland и Plasma.
hl.bind(mainMod .. " + F1", hl.dsp.exec_cmd("flyarchos-performance toggle"))

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
