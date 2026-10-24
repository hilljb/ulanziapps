# @name    Glucose
# @config  source text "Reading URL" default="http://192.168.1.177:8765/"
# @config  every  number "Refresh" default=60 min=15 max=300 unit=s

# The clock asks the Mac for one line, such as "128 mg/dl".
# The Mac holds the Firestore key. This file does not.
# Digits are a 3x5 pattern drawn at 2x (6x10). The units stay in the
# large font (7px) and share the digits' baseline.

class Glucose
  var label, ticks, number, units, glyphs, scale, digit_gap

  def init()
    self.label = "..."
    self.ticks = 0
    self.scale = 2
    self.digit_gap = 1
    self.glyphs = self.digit_glyphs()
    self.split_label()
  end

  def loop()
    if self.ticks <= 0
      self.ticks = int(store.get("every"))
      http.get(store.get("source"), / body, status -> self.on_body(body, status))
    end
    self.ticks -= 1
  end

  def on_body(body, status)
    if body == nil return end
    if status != 200 return end
    self.label = body
    self.split_label()
  end

  def draw()
    clear()
    if !self.digits_only(self.number)
      self.draw_plain(self.label)
      return
    end
    font("large")
    var nw = self.number_width()
    var uw = 0
    var gap = 0
    if self.units != ""
      uw = text_ink_width(self.units)
      gap = 2
    end
    var x = int((width() - nw - gap - uw) / 2)
    # 10px digits ending on row 10, the large-font baseline at y = 10.
    self.draw_number(x, 1, 0xFFFFFF)
    if self.units != ""
      text(x + nw + gap, 10, self.units, 0xFFFFFF)
    end
  end

  def draw_plain(label)
    font("large")
    text((width() - text_ink_width(label)) / 2, 10, label, 0xFFFFFF)
  end

  def split_label()
    import string
    var parts = string.split(self.label, " ")
    self.number = parts[0]
    self.units = ""
    if size(parts) > 1
      self.units = parts[1]
    end
  end

  def digits_only(s)
    if s == nil || size(s) == 0 return false end
    var i = 0
    while i < size(s)
      if self.glyphs.find(s[i]) == nil return false end
      i += 1
    end
    return true
  end

  def number_width()
    var n = size(self.number)
    var dw = 3 * self.scale
    return n * dw + (n - 1) * self.digit_gap
  end

  def draw_number(x, y, color)
    var i = 0
    var cursor = x
    var s = self.number
    while i < size(s)
      if i > 0 cursor += self.digit_gap end
      cursor = self.draw_digit(cursor, y, s[i], color)
      i += 1
    end
  end

  def draw_digit(x, y, code, color)
    var rows = self.glyphs.find(code)
    var scale = self.scale
    var sy = 0
    for row : rows
      var sx = 0
      for bit : row
        if bit == 1
          rect_fill(x + sx * scale, y + sy * scale, scale, scale, color)
        end
        sx += 1
      end
      sy += 1
    end
    return x + 3 * scale
  end

  def digit_glyphs()
    return {
      "0": [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
      "1": [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[1,1,1]],
      "2": [[1,1,1],[0,0,1],[1,1,1],[1,0,0],[1,1,1]],
      "3": [[1,1,1],[0,0,1],[1,1,1],[0,0,1],[1,1,1]],
      "4": [[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1]],
      "5": [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
      "6": [[1,1,1],[1,0,0],[1,1,1],[1,0,1],[1,1,1]],
      "7": [[1,1,1],[0,0,1],[0,0,1],[0,0,1],[0,0,1]],
      "8": [[1,1,1],[1,0,1],[1,1,1],[1,0,1],[1,1,1]],
      "9": [[1,1,1],[1,0,1],[1,1,1],[0,0,1],[1,1,1]]
    }
  end
end

return Glucose()
