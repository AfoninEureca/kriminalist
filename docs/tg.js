/* Центр «Контур» внутри Telegram: тема, кнопка «Назад», вибрация и сдача протокола в бот.
   Вне Telegram файл ничего не делает. */
(function () {
  'use strict';
  var tg = window.Telegram && window.Telegram.WebApp;
  if (!tg || !tg.initData) return;
  var root = document.documentElement, scene = window.KONTUR_SCENE || 0;
  try { tg.ready(); tg.expand(); if (tg.disableVerticalSwipes) tg.disableVerticalSwipes(); } catch (e) { /* старый клиент */ }
  function theme() {
    var dark = tg.colorScheme === 'dark';
    root.setAttribute('data-theme', dark ? 'dark' : 'light');
    try { tg.setHeaderColor(dark ? '#14110e' : '#efe8dc'); tg.setBackgroundColor(dark ? '#14110e' : '#efe8dc'); } catch (e) { /* нет поддержки */ }
  }
  theme(); tg.onEvent('themeChanged', theme);
  root.classList.add('in-tg');

  /* «Назад»: закрыть карточку, иначе вернуться в каталог */
  if (scene) {
    tg.BackButton.show();
    tg.BackButton.onClick(function () {
      var sh = document.getElementById('sheet');
      if (sh && !sh.hidden) { sh.dispatchEvent(new MouseEvent('click', { bubbles: true })); return; }
      location.href = 'index.html';
    });
  }

  /* лёгкая вибрация на нажатия кнопок игры */
  document.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('button,.tab')) { try { tg.HapticFeedback.selectionChanged(); } catch (err) { /* нет */ } }
  }, true);

  /* сдать протокол: кнопка появляется, когда дело закрыто или проиграно */
  if (!scene) return;
  var shown = false;
  function payload() {
    var prot = document.getElementById('d-prot'), st = document.querySelector('.stars');
    var stars = 0;
    if (st) { var m = /(\d)\s*из\s*3/.exec(st.getAttribute('aria-label') || ''); stars = m ? +m[1] : 0; }
    var win = !!document.querySelector('.note.win, .win');
    var text = prot ? prot.value : '';
    var data = { t: 'run', s: scene, w: win ? 1 : 0, st: win ? stars : 0, p: text };
    var json = JSON.stringify(data);
    while (new Blob([json]).size > 4000 && data.p.length > 50) { data.p = data.p.slice(0, Math.floor(data.p.length * 0.85)); json = JSON.stringify(data); }
    return json;
  }
  setInterval(function () {
    var has = !!document.getElementById('d-prot');
    if (has && !shown) {
      shown = true;
      tg.MainButton.setText('Сдать протокол в бот');
      tg.MainButton.show();
      try { tg.HapticFeedback.notificationOccurred('success'); } catch (e) { /* нет */ }
    } else if (!has && shown) { shown = false; tg.MainButton.hide(); }
  }, 700);
  tg.MainButton.onClick(function () {
    if (tg.initDataUnsafe && tg.initDataUnsafe.query_id) {
      var prot = document.getElementById('d-prot');
      try { navigator.clipboard.writeText(prot ? prot.value : ''); } catch (e) { /* без буфера */ }
      tg.showAlert('Игра открыта не из меню бота, поэтому протокол нельзя сдать напрямую. Он скопирован: вставьте его боту сообщением или откройте игру кнопкой «🎮 Играть» под полем ввода.');
      return;
    }
    try { tg.sendData(payload()); }
    catch (e) { tg.showAlert('Протокол можно сдать, только если игра открыта кнопкой «Играть» под полем ввода в боте. Скопируйте протокол и пришлите его боту сообщением.'); }
  });
})();
