(function () {
  // Утилита: получить элемент по селектору
  function $(selector) {
    return document.querySelector(selector);
  }

  // Утилита: показать/скрыть блок по селектору
  function setVisible(selector, visible) {
    var el = $(selector);
    if (!el) return;
    if (visible) {
      el.classList.remove("event-hidden");
    } else {
      el.classList.add("event-hidden");
    }
  }

  // Найдём строки полей по классам "field-<name>"
  function showDateGroup(show) {
    setVisible(".field-start_datetime", show);
    setVisible(".field-end_datetime", show);
    setVisible(".field-duration_minutes", show);
    // RRULE показывается только для "дата+повтор"
    // управим отдельно в applyVisibility()
  }

  function showMonthGroup(show) {
    setVisible(".field-date_mode", show);
    setVisible(".field-month_year", show);
    setVisible(".field-month_number", show);
    setVisible(".field-is_recurring_monthly", show);
    setVisible(".field-month_interval", show);
  }

  // Создаём контейнер для переключателей
  function insertToggles() {
    var timeFieldset = document.querySelector("fieldset.module:has(.field-start_datetime)") ||
                       document.querySelector("fieldset.module:has(.field-date_mode)");
    if (!timeFieldset) {
      // если не нашли по современному :has(), пробуем ближайший по .module
      var modules = document.querySelectorAll("fieldset.module");
      if (modules && modules.length > 0) timeFieldset = modules[0];
    }
    if (!timeFieldset) return;

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

    // Вставим переключатели перед секцией "Time & Recurrence"
    timeFieldset.parentNode.insertBefore(wrapper, timeFieldset);

    return {
      bindRadios: wrapper.querySelectorAll('input[name="bind_type"]'),
      repeatRadios: wrapper.querySelectorAll('input[name="repeat_type"]')
    };
  }

  // Применить видимость полей в зависимости от выбранных радиокнопок
  function applyVisibility(bindValue, repeatValue) {
    var isDate = bindValue === "date";
    var isMonth = bindValue === "month";
    var isRecurring = repeatValue === "recurring";

    // Группы
    showDateGroup(isDate);
    showMonthGroup(isMonth);

    // RRULE виден только для "дата + повтор"
    var showRRule = isDate && isRecurring;
    setVisible(".field-recurrence", showRRule);

    // Для "месяц + повтор" — показываем is_recurring_monthly и month_interval (у нас уже виден весь блок)
    // Для "месяц + один раз" — скроем чекбокс повторяемости и интервал
    setVisible(".field-is_recurring_monthly", isMonth && isRecurring);
    setVisible(".field-month_interval", isMonth && isRecurring);
  }

  // Подставить дефолтные значения при выборе "месяц"
  function applyMonthDefaults(isRecurring) {
    var now = new Date();
    var yearField = $("#id_month_year");
    var monthField = $("#id_month_number");
    var modeField = $("#id_date_mode");
    var monthlyFlag = $("#id_is_recurring_monthly");
    var intervalField = $("#id_month_interval");

    if (modeField && (!modeField.value || modeField.value !== "number_of_month")) {
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

  // При смене пользователя — подставить дефолтный аккаунт
  function bindUserAccountAutofill() {
    var userSelect = $("#id_user");
    var accountSelect = $("#id_account");
    if (!userSelect || !accountSelect) return;

    function onUserChange() {
      var userId = userSelect.value;
      if (!userId) return;

      // Небольшой запрос в наш кастомный эндпоинт
      var url = window.location.origin + "/admin/schedule/event/default-account/?user_id=" + encodeURIComponent(userId);

      fetch(url, { credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data) return;
          var accId = data.account_id;
          if (!accId) return;

          // Поставим найденный аккаунт как выбранный
          var options = accountSelect.options;
          for (var i = 0; i < options.length; i += 1) {
            var opt = options[i];
            if (String(opt.value) === String(accId)) {
              accountSelect.value = String(accId);
              break;
            }
          }
        })
        .catch(function () { /* тихо игнорируем */ });
    }

    userSelect.addEventListener("change", onUserChange);
  }

  // Инициализация
  function init() {
    // Вставляем переключатели
    var toggles = insertToggles();
    if (!toggles) return;

    var bindRadios = toggles.bindRadios;
    var repeatRadios = toggles.repeatRadios;

    // Значения по умолчанию: определим из текущей формы
    var currentBind = "date";
    var currentRepeat = "single";

    var modeField = $("#id_date_mode");
    if (modeField && modeField.value === "number_of_month") currentBind = "month";

    var monthlyFlag = $("#id_is_recurring_monthly");
    if (monthlyFlag && monthlyFlag.checked) currentRepeat = "recurring";

    // Выставляем радио по текущему состоянию
    for (var i = 0; i < bindRadios.length; i += 1) {
      var r = bindRadios[i];
      r.checked = (r.value === currentBind);
      r.addEventListener("change", function (e) {
        var bindValue = e.target.value;
        var repeatValue = getCheckedValue(repeatRadios);

        if (bindValue === "month") {
          var isRecurring = repeatValue === "recurring";
          applyMonthDefaults(isRecurring);
        }
        applyVisibility(bindValue, repeatValue);
      });
    }

    for (var j = 0; j < repeatRadios.length; j += 1) {
      var rr = repeatRadios[j];
      rr.checked = (rr.value === currentRepeat);
      rr.addEventListener("change", function (e) {
        var repeatValue = e.target.value;
        var bindValue = getCheckedValue(bindRadios);

        if (bindValue === "month") {
          var isRecurring = repeatValue === "recurring";
          applyMonthDefaults(isRecurring);
        }
        applyVisibility(bindValue, repeatValue);
      });
    }

    // Применим видимость один раз при старте
    applyVisibility(currentBind, currentRepeat);
    if (currentBind === "month") {
      applyMonthDefaults(currentRepeat === "recurring");
    }

    // Автоподстановка аккаунта по пользователю
    bindUserAccountAutofill();
  }

  function getCheckedValue(nodeList) {
    for (var i = 0; i < nodeList.length; i += 1) {
      var r = nodeList[i];
      if (r.checked) return r.value;
    }
    return null;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
