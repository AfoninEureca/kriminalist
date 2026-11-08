/* Штаб «Меридиан» внутри Telegram: тема, «Назад» в каталог и сдача протокола эпизода в бот. */
(function () {
  'use strict';
  var tg = window.Telegram && window.Telegram.WebApp;
  if (!tg || !tg.initData) return;
  try { tg.ready(); tg.expand(); if (tg.disableVerticalSwipes) tg.disableVerticalSwipes(); } catch (e) {}
  try { tg.BackButton.show(); tg.BackButton.onClick(function () { location.href = 'index.html'; }); } catch (e) {}
  var shown = false;
  function result() {
    var m = document.querySelector('#ov .modal');
    if (!m || !/Заключение принято/.test(m.textContent)) return null;
    var n = /Эпизод\s+(\d+)\s+закрыт/.exec(m.textContent);
    var st = document.querySelector('#ov .stars');
    var k = st ? /(\d)\s*из\s*3/.exec(st.getAttribute('aria-label') || '') : null;
    if (!n) return null;
    return { s: +n[1], st: k ? +k[1] : 1, p: m.innerText.replace(/\s+\n/g, '\n').slice(0, 1500) };
  }
  setInterval(function () {
    var r = result();
    if (r && !shown) { shown = true; tg.MainButton.setText('Сдать протокол в бот'); tg.MainButton.show(); try { tg.HapticFeedback.notificationOccurred('success'); } catch (e) {} }
    else if (!r && shown) { shown = false; tg.MainButton.hide(); }
  }, 700);
  tg.MainButton.onClick(function () {
    var r = result(); if (!r) return;
    if (tg.initDataUnsafe && tg.initDataUnsafe.query_id) {
      tg.showAlert('Игра открыта не из меню бота, поэтому протокол нельзя сдать напрямую. Откройте игру кнопкой «🎮 Играть» под полем ввода.');
      return;
    }
    try { tg.sendData(JSON.stringify({ t: 'run', s: r.s, w: 1, st: r.st, p: r.p })); }
    catch (e) { tg.showAlert('Протокол можно сдать, только если игра открыта кнопкой «Играть» под полем ввода в боте.'); }
  });
})();
