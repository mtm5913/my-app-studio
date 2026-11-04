/* Tab-memory conversation only. All model/user content is rendered as text. */
(() => {
  const form = document.querySelector('#chat-form');
  if (!form) return;
  const question = form.querySelector('#question');
  const send = document.querySelector('#send-question');
  const stop = document.querySelector('#stop-answer');
  const fresh = document.querySelector('#new-chat');
  const log = document.querySelector('#conversation');
  const status = document.querySelector('#chat-status');
  const error = document.querySelector('#chat-error');
  let history = [];
  let controller = null;

  function message(speaker, text) {
    const card = document.createElement('article');
    card.className = 'chat-message ' + (speaker === 'You' ? 'from-you' : 'from-olive');
    const name = document.createElement('h2');
    name.textContent = speaker;
    const content = document.createElement('p');
    content.className = 'answer-text';
    content.textContent = text;
    card.append(name, content);
    log.append(card);
    return {card, content};
  }

  function showSources(card, sources) {
    if (!sources.length) return;
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'Retrieved USDA sources';
    details.append(summary);
    for (const source of sources) {
      const link = document.createElement('a');
      const url = new URL(source.url);
      if (url.protocol !== 'https:') continue;
      link.href = url.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = '[' + source.id + '] ' + source.title;
      const excerpt = document.createElement('p');
      excerpt.textContent = source.excerpt;
      details.append(link, excerpt);
    }
    card.append(details);
  }

  fresh.addEventListener('click', () => {
    history = [];
    log.replaceChildren();
    question.value = '';
    error.hidden = true;
    status.textContent = 'A fresh conversation, at your pace.';
    form.querySelector('label[for="question"]').textContent = 'Your food question';
    question.focus();
  });
  stop.addEventListener('click', () => controller?.abort());

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (controller || !form.reportValidity()) return;
    const text = question.value.trim();
    if (text.length < 3) return;
    error.hidden = true;
    message('You', text);
    const reply = message('Olive', '');
    reply.card.setAttribute('aria-busy', 'true');
    status.textContent = 'Finding relevant USDA passages…';
    send.disabled = true;
    fresh.disabled = true;
    stop.hidden = false;
    controller = new AbortController();
    let completed = false;
    let buffer = '';
    try {
      const response = await fetch('/api/food-chat/stream', {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': form.elements.csrf_token.value},
        body: JSON.stringify({question: text, share_question: form.elements.share_question.checked, history})
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(typeof body.detail === 'string' ? body.detail : 'Check your question and try again.');
      }
      if (!response.body) throw new Error('Streaming is unavailable in this browser.');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      function consume(line) {
        if (!line.trim()) return;
        const update = JSON.parse(line);
        if (update.type === 'sources') showSources(reply.card, update.sources);
        if (update.type === 'delta') {
          reply.content.textContent += update.text;
          status.textContent = 'Olive is answering…';
        }
        if (update.type === 'error') throw new Error(update.message);
        if (update.type === 'done') completed = true;
      }
      while (true) {
        const {value, done} = await reader.read();
        buffer += decoder.decode(value, {stream: !done});
        let newline;
        while ((newline = buffer.indexOf('\n')) >= 0) {
          consume(buffer.slice(0, newline));
          buffer = buffer.slice(newline + 1);
        }
        if (done) break;
      }
      if (buffer.trim()) consume(buffer);
      if (!completed) throw new Error('The connection ended before Olive finished. Please try again.');
      history.push({role: 'user', content: text}, {role: 'assistant', content: reply.content.textContent.slice(0, 4000)});
      history = history.slice(-6);
      while (history.reduce((total, m) => total + m.content.length, 0) > 12000) history.splice(0, 2);
      question.value = '';
      form.querySelector('label[for="question"]').textContent = 'Ask another food question';
      status.textContent = 'Answer complete. You can ask a follow-up below.';
    } catch (failure) {
      reply.card.classList.add('incomplete');
      error.textContent = failure.name === 'AbortError'
        ? 'Answer stopped. Any text shown is incomplete and won’t be used for follow-ups.'
        : failure.message + ' Any partial answer won’t be used for follow-ups.';
      error.hidden = false;
      status.textContent = 'The answer did not finish.';
    } finally {
      controller = null;
      reply.card.setAttribute('aria-busy', 'false');
      send.disabled = false;
      fresh.disabled = false;
      stop.hidden = true;
      question.focus();
    }
  });
})();
