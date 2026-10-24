# @name    Trend
# @config  source text "Reading URL" default="http://192.168.1.177:8765/trend"
# @config  every  number "Refresh" default=60 min=15 max=300 unit=s

# The clock asks the Mac for "age|diff", such as "4m ago|+7 mg/dl".
# The top line is how many minutes have passed since the reading.
# The bottom line is the change since the previous reading, rounded.
# The Mac holds the Firestore key. This file does not.

class Trend
  var when_label, diff_left, diff_right, diff_full, diff_through_slash, has_slash, ticks

  def init()
    self.when_label = "..."
    self.diff_left = ""
    self.diff_right = ""
    self.diff_full = ""
    self.diff_through_slash = ""
    self.has_slash = false
    self.ticks = 0
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
    import string
    var parts = string.split(body, "|")
    self.when_label = parts[0]
    self.diff_left = ""
    self.diff_right = ""
    self.diff_full = ""
    self.diff_through_slash = ""
    self.has_slash = false
    if size(parts) > 1
      var bits = string.split(parts[1], "/")
      self.diff_left = bits[0]
      self.diff_full = parts[1]
      if size(bits) > 1
        self.has_slash = true
        self.diff_right = bits[1]
        self.diff_through_slash = bits[0] + "/"
      end
    end
  end

  def draw()
    clear()
    font("large")
    if self.diff_full == ""
      text((width() - text_ink_width(self.when_label)) / 2, 10, self.when_label, 0xFFFFFF)
      return
    end
    # Two large lines. y is the baseline. "g" descends one row, so the
    # lower line stops on the last row. The slash is drawn one row lower
    # so its top clears the descender in "ago".
    text((width() - text_ink_width(self.when_label)) / 2, 6, self.when_label, 0xFFFFFF)
    if !self.has_slash
      text((width() - text_ink_width(self.diff_full)) / 2, 14, self.diff_full, 0xFFFFFF)
      return
    end
    var x0 = (width() - text_ink_width(self.diff_full)) / 2
    text(x0, 14, self.diff_left, 0xFFFFFF)
    var slash_x = x0 + text_ink_width(self.diff_through_slash) - text_ink_width("/")
    text(slash_x, 15, "/", 0xFFFFFF)
    var right_x = x0 + text_ink_width(self.diff_full) - text_ink_width(self.diff_right)
    text(right_x, 14, self.diff_right, 0xFFFFFF)
  end
end

return Trend()
