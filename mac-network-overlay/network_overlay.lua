local mp = require 'mp'
local assdraw = require 'mp.assdraw'
local options = require 'mp.options'
local opts = { enabled = true, scale = 1.0, corner = 'top-right' }
options.read_options(opts, 'piliplus_net')

local overlay = mp.create_osd_overlay('ass-events')
local last_data = nil
local enabled = opts.enabled
local scale = math.max(0.7, math.min(1.6, tonumber(opts.scale) or 1))
local corner = opts.corner

local function format_speed(rate)
    if rate >= 1000000 then return string.format('%.2f MB/s', rate / 1000000) end
    if rate >= 1000 then return string.format('%.0f KB/s', rate / 1000) end
    return string.format('%.0f B/s', rate)
end

local function publish(active, rate, buffer, waiting)
    mp.set_property_native('user-data/piliplus-network', {
        ready = true, enabled = enabled, visible = active,
        bytes_per_second = rate, buffered_seconds = buffer,
        buffering = waiting,
        scale = scale, corner = corner,
    })
end

local function update()
    local dimensions = mp.get_property_native('video-out-params')
    local cache = mp.get_property_native('demuxer-cache-state') or {}
    local rate = tonumber(cache['raw-input-rate']) or mp.get_property_number('cache-speed', 0)
    rate = math.max(0, rate or 0)
    local buffer = mp.get_property_number('demuxer-cache-duration')
    local waiting = mp.get_property_bool('paused-for-cache', false)
    local path = mp.get_property('path', '')
    local network = path:match('^https?://') or path:match('^edl://')
    local active = enabled and dimensions ~= nil and network ~= nil
        and not mp.get_property_bool('idle-active', true)
        and not mp.get_property_bool('eof-reached', false)
    publish(active and true or false, rate, buffer, waiting)
    if not active then
        if last_data ~= nil then overlay:remove(); last_data = nil end
        return
    end

    local width, height = mp.get_osd_size()
    if not width or not height or width < 1 or height < 1 then return end
    -- Normalize to the video viewport rather than the source's 4K/8K size.
    -- This keeps the panel legible with Flutter's texture scaling.
    local res_y = 720
    local res_x = width / height * res_y
    local speed = format_speed(rate)
    local label = buffer and string.format('缓冲 %.1fs', math.max(0, buffer)) or '缓冲 —'
    -- Menlo has fixed-width ASCII glyphs. Keep a small, constant gap after
    -- the speed instead of reserving an empty column for longer values.
    local speed_width = #speed * 19 * 0.602
    local label_width = 2 * 19 + #(label:gsub('缓冲', '')) * 19 * 0.602
    local inline_width = 24 + speed_width + 9 + label_width
    local stacked_width = 24 + math.max(speed_width, label_width)
    local s = math.min(scale, math.max(0.7, (res_x - 36) / stacked_width))
    local stacked = inline_width * s > res_x - 36
    local box_w, box_h = (stacked and stacked_width or inline_width) * s, (stacked and 48 or 25) * s
    local left = corner == 'top-left' or corner == 'bottom-left'
    local bottom = corner == 'bottom-left' or corner == 'bottom-right'
    local x = left and 18 or math.max(12, res_x - box_w - 18)
    local y = bottom and (res_y - box_h - 18) or 18
    local ass = assdraw.ass_new()
    -- Plain text only: no filled background or separator. A fine dark
    -- outline keeps the white text readable over bright video scenes.
    local outline = string.format('\\bord%.2f\\shad0\\3c&H101010&\\3a&H35&', 0.8*s)
    ass:new_event()
    ass:append(string.format('{\\an7\\pos(%.1f,%.1f)\\fnPingFang SC\\fs%.1f%s\\1c&HCEC18B&}↓', x, y - 2*s, 23*s, outline))
    ass:new_event()
    ass:append(string.format('{\\an7\\pos(%.1f,%.1f)\\fnMenlo\\fs%.1f%s\\1c&HF8F6F2&}%s', x + 24*s, y, 19*s, outline, speed))
    local color = waiting and 'B9D8FF' or 'F8F6F2'
    ass:new_event()
    ass:append(string.format('{\\an7\\pos(%.1f,%.1f)\\fnMenlo\\fs%.1f%s\\1c&H%s&}%s', x + (stacked and 24 or (24 + speed_width + 9))*s, y + (stacked and 25 or 0)*s, 19*s, outline, color, label))
    overlay.res_x, overlay.res_y = res_x, res_y
    overlay.z = 30
    local signature = ass.text .. ':' .. tostring(res_x)
    if last_data ~= signature then
        overlay.data = ass.text
        overlay:update()
        last_data = signature
    end
end

mp.register_script_message('piliplus-network-set', function(value)
    enabled = value == 'yes'
    update()
end)
mp.register_script_message('piliplus-network-toggle', function()
    enabled = not enabled
    update()
end)
mp.register_script_message('piliplus-network-size', function(value)
    local number = tonumber(value)
    if number then scale = math.max(0.7, math.min(1.6, number)); update() end
end)
mp.register_script_message('piliplus-network-corner', function(value)
    if value == 'top-right' or value == 'top-left' or value == 'bottom-right' or value == 'bottom-left' then
        corner = value; update()
    end
end)
mp.register_event('file-loaded', update)
mp.register_event('end-file', function() overlay:remove(); last_data = nil end)
mp.observe_property('osd-dimensions', 'native', update)
mp.add_periodic_timer(0.5, update)
update()
