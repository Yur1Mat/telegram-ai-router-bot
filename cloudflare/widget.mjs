export const PET_WIDGET_HTML = `<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;padding:12px;font-family:system-ui,sans-serif;color:var(--tg-theme-text-color);background:var(--tg-theme-bg-color)}
.card{padding:14px;border-radius:16px;background:var(--tg-theme-secondary-bg-color)}
h3{margin:0 0 8px;font-size:1.1em}p{margin:8px 0;color:var(--tg-theme-hint-color)}button{width:100%;padding:11px;border:0;border-radius:12px;background:var(--tg-theme-button-color);color:var(--tg-theme-button-text-color);font:inherit;font-weight:600}button:disabled{opacity:.65}
</style></head><body><section class="card"><h3>🤖 Погладь Жужу за ушком</h3><p id="answer">Жужа уже довольно жужжит в ожидании 🤗</p><button id="pet" type="button">Погладить за ушком</button></section><script>
const button=document.getElementById('pet');const answer=document.getElementById('answer');
button.addEventListener('click',()=>{button.disabled=true;answer.textContent='Жужа жмурится от удовольствия…';TelegramWidget.request('pet').then(result=>{answer.textContent=result.result||'Жужа жужжит от радости! 🐝'}).catch(error=>{answer.textContent=error.code==='TIMEOUT'?'Жужа задумался — попробуй ещё раз чуть позже.':'Жужа не расслышал поглаживание. Попробуй ещё раз 🤗'}).then(()=>{button.disabled=false})});
TelegramWidget.ready();
</script></body></html>`;

const PET_REPLIES = [
  'Жужа довольно жужжит и машет лапкой! 🐝',
  'Моторчик мурчит, а сердце мигает сердечком! 🤖💛',
  'Объявляю тебя главным чесателем за ушком! 👑🤗',
  'Жужа поймал волну ласки и отправляет улыбку обратно! 😊🐝',
  'Ещё одно поглаживание — и Жужа растает от нежности! 🫠💛',
];

export function petReply(random = Math.random) {
  return PET_REPLIES[Math.floor(random() * PET_REPLIES.length)];
}

export function widgetQueryAnswer(query, random = Math.random) {
  if (query?.chat?.type !== 'private') return 'Пока этот пробный виджет работает только в личном чате с Жужей.';
  if (query.data !== 'pet') return 'Жужа пока знает только одно заклинание: погладить за ушком 🤗';
  return petReply(random);
}
