(function () {
  function log() {
    if (window && window.console && console.log) {
      var args = Array.prototype.slice.call(arguments);
      args.unshift("[event_admin]");
      console.log.apply(console, args);
    }
  }

  function $(sel) { return document.querySelector(sel); }
  function addClass(el, cls) { if (el && !el.classList.contains(cls)) el.classList.add(cls); }
  function removeClass(el, cls) { if (el && el.classList.contains(cls)) el.classList.remove(cls); }
  function setVisible(selector, visible) {
    var el = $(selector);
    if (!el) return;
    if (visible) removeClass(el, "event-hidden");
    else addClass(el, "event-hidden");
  }

  function findTimeFieldset() {
    // Ищем любой элемент поля даты и поднимаемся к ближайшему fieldset
    var startField = document.querySelector(".field-start_datetime");
    if (startField) {
      var fs = startField.closest("fieldset");
      if (fs) return fs;
    }
    // Фолбэк: берём первый .module (обычно это и есть секция)
    var modules = document.querySelectorAll("fieldset.module");
    if (modules && modules.length) return modules[0];
    return null;
  }

  function showDateGroup(show) {
    setVisible(".field-start_datetime", show);
    setVisible(".field-end_datetime", show);
    setVisible(".field-duration_minutes", show);
  }

  function showMonthGroup(show) {
    setVisible(".field-date_mode", show);
    setVisible(".field-month_year", show);
    setVisible(".field-month_number", show);
    setVisible(".field-is_recurring_monthly", show);
    setVisible(".field-month_interval", show);
  }

  function getCheckedValue(nodeList) {
    if (!nodeList) return null;
    for (var i = 0; i < nodeList.length; i += 1) {
      var r = nodeList[i];
      if (r.checked) return r.value;
    }
    return null;
  }

  function applyVisibility(bindValue, repeatValue) {
    var isDate = bindValue === "date";
    var isMonth = bindValue === "month";
    var isRecurring = repeatValue === "recurring";

    showDateGroup(isDate);
    showMonthGroup(isMonth);

    // RRULE показываем только при "дата + повтор"
    setVisible(".field-recurrence", isDate && isRecurring);

    // Для месячного режима скрываем/показываем чекбокс и интервал
    setVisible(".field-is_recurring_monthly", isMonth && isRecurring);
    setVisible(".field-month_interval", isMonth && isRecurring);
    setVisible(".field-months_span", isMonth && isRecurring);
  }

  function applyMonthDefaults(isRecurring) {
    var now = new Date();
    var yearField = $("#id_month_year");
    var monthField = $("#id_month_number");
    var modeField = $("#id_date_mode");
    var monthlyFlag = $("#id_is_recurring_monthly");
    var intervalField = $("#id_month_interval");

    if (modeField && modeField.value !== "number_of_month") {
      modeField.value = "number_of_month";
    }
    if (yearField && !yearField.value) yearField.value = String(now.getFullYear());
    if (monthField && !monthField.value) monthField.value = String(now.getMonth() + 1);

    if (isRecurring) {
      if (monthlyFlag) monthlyFlag.checked = true;
      if (intervalField && !intervalField.value) intervalField.value = "1";
    } else {
      if (monthlyFlag) monthlyFlag.checked = false;
    }
  }

  function bindUserAccountAutofill() {
    var userSelect = $("#id_user");
    var accountSelect = $("#id_account");
    if (!userSelect || !accountSelect) return;

    function onUserChange() {
      var userId = userSelect.value;
      if (!userId) return;

      // эндпоинт из admin.get_urls
      var url = window.location.origin + "/admin/schedule/event/default-account/?user_id=" + encodeURIComponent(userId);

      fetch(url, { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (!data || !data.account_id) return;
          var target = String(data.account_id);
          var options = accountSelect.options;
          for (var i = 0; i < options.length; i += 1) {
            if (String(options[i].value) === target) {
              accountSelect.value = target;
              break;
            }
          }
        })
        .catch(function (e) { log("autofill error", e); });
    }

    userSelect.addEventListener("change", onUserChange);
  }

  function insertToggles() {
    var timeFieldset = findTimeFieldset();
    if (!timeFieldset) { log("time fieldset not found"); return null; }

    var wrapper = document.createElement("div");
    wrapper.className = "event-toggles";

    var bindLabel = document.createElement("div");
    bindLabel.className = "event-toggle-label";
    bindLabel.textContent = "Тип привязки:";

    var bindControls = document.createElement("div");
    bindControls.className = "event-toggle-group";
    bindControls.innerHTML =
      '<label><input type="radio" name="bind_type" value="date"> Дата</label>' +
      '<label><input type="radio" name="bind_type" value="month"> Месяц</label>';

    var repeatLabel = document.createElement("div");
    repeatLabel.className = "event-toggle-label";
    repeatLabel.textContent = "Повторяемость:";

    var repeatControls = document.createElement("div");
    repeatControls.className = "event-toggle-group";
    repeatControls.innerHTML =
      '<label><input type="radio" name="repeat_type" value="single"> Один раз</label>' +
      '<label><input type="radio" name="repeat_type" value="recurring"> Повтор</label>';

    wrapper.appendChild(bindLabel);
    wrapper.appendChild(bindControls);
    wrapper.appendChild(repeatLabel);
    wrapper.appendChild(repeatControls);

    // Вставим ПЕРЕД секцией Time & Recurrence (или над первым fieldset)
    timeFieldset.parentNode.insertBefore(wrapper, timeFieldset);

    return {
      bindRadios: wrapper.querySelectorAll('input[name="bind_type"]'),
      repeatRadios: wrapper.querySelectorAll('input[name="repeat_type"]')
    };
  }

  function init() {
    log("init start");
    var toggles = insertToggles();
    if (!toggles) { log("toggles not inserted"); return; }

    var bindRadios = toggles.bindRadios;
    var repeatRadios = toggles.repeatRadios;

    // Текущее состояние формы → какие радио активировать
    var currentBind = "date";
    var currentRepeat = "single";

    var modeField = $("#id_date_mode");
    if (modeField && modeField.value === "number_of_month") currentBind = "month";

    var monthlyFlag = $("#id_is_recurring_monthly");
    if (monthlyFlag && monthlyFlag.checked) currentRepeat = "recurring";

    // Проставляем checked и обработчики
    for (var i = 0; i < bindRadios.length; i += 1) {
      var r = bindRadios[i];
      r.checked = (r.value === currentBind);
      r.addEventListener("change", function (e) {
        var bindValue = e.target.value;
        var repeatValue = getCheckedValue(repeatRadios);
        if (bindValue === "month") applyMonthDefaults(repeatValue === "recurring");
        applyVisibility(bindValue, repeatValue);
      });
    }

    for (var j = 0; j < repeatRadios.length; j += 1) {
      var rr = repeatRadios[j];
      rr.checked = (rr.value === currentRepeat);
      rr.addEventListener("change", function (e) {
        var repeatValue = e.target.value;
        var bindValue = getCheckedValue(bindRadios);
        if (bindValue === "month") applyMonthDefaults(repeatValue === "recurring");
        applyVisibility(bindValue, repeatValue);
      });
    }

    // Первичное применение
    applyVisibility(currentBind, currentRepeat);
    if (currentBind === "month") applyMonthDefaults(currentRepeat === "recurring");

    // Автоподстановка аккаунта при смене пользователя
    bindUserAccountAutofill();

    log("init done");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
