// ========== Blog AI Chat - Digital Twin ==========

(function () {
  // Backend API (set to empty string when running locally without backend)
  // When backend is running, set to 'http://localhost:8000'
  const API_BASE = window.CHAT_API_BASE || 'https://formerly-index-collected-bold.trycloudflare.com';
  const POSTS_FILE = 'data/posts.json';

  let posts = [];
  let chatHistory = [];
  let isOpen = false;

  // Session ID - persisted in localStorage
  function getSessionId() {
    let id = localStorage.getItem('chat_session_id');
    if (!id) {
      id = 's_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
      localStorage.setItem('chat_session_id', id);
    }
    return id;
  }

  // ========== Init ==========
  async function initChat() {
    try {
      const res = await fetch(POSTS_FILE);
      posts = await res.json();
    } catch (e) {
      posts = [];
    }

    injectHTML();
    bindEvents();
  }

  function injectHTML() {
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = 'static/css/chat.css';
    document.head.appendChild(css);

    const html = `
      <button class="chat-fab" id="chatFab" title="和我聊聊">&#128172;</button>

      <div class="chat-panel" id="chatPanel">
        <div class="chat-header" style="position:relative;">
          <h3>问我的数字分身</h3>
          <div class="chat-header-actions">
            <button onclick="ChatBot.toggle()" title="关闭">&times;</button>
          </div>
        </div>

        <div class="chat-messages" id="chatMessages">
          <div class="chat-msg system">我是杨轩，一个真实的开发者，不是什么AI模型。随便问，聊聊技术、工作、生活都行。</div>
        </div>

        <div class="chat-suggestions" id="chatSuggestions">
          <button onclick="ChatBot.ask('你平时工作做什么？')">你的工作具体做什么</button>
          <button onclick="ChatBot.ask('INFJ对你工作有什么影响')">INFJ对你工作有什么影响</button>
          <button onclick="ChatBot.ask('你的个人主页什么样')">你的个人主页什么样</button>
          <button onclick="ChatBot.ask('你最近在忙什么？')">你最近在忙什么</button>
          <button onclick="ChatBot.ask('你喜欢什么类型的游戏')">我喜欢什么类型的游戏</button>
          <button onclick="ChatBot.ask('你是什么技术栈？')">你是什么技术栈？</button>
          <button onclick="ChatBot.ask('平时怎么学习新技术？')">怎么学AI技术</button>
        </div>

        <div class="chat-input-area">
          <input type="text" id="chatInput" placeholder="随便问，不用客气..." autocomplete="off">
          <button onclick="ChatBot.send()">发送</button>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', html);
  }

  function bindEvents() {
    document.getElementById('chatFab').addEventListener('click', toggle);
    document.getElementById('chatInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });
    const inlineInput = document.getElementById('inlineChatInput');
    if (inlineInput) {
      inlineInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          inlineSend();
        }
      });
    }
  }

  // ========== Toggle ==========
  function toggle() {
    isOpen = !isOpen;
    document.getElementById('chatPanel').classList.toggle('open', isOpen);
    document.getElementById('chatFab').classList.toggle('hidden', isOpen);
    if (isOpen) {
      document.getElementById('chatInput').focus();
    }
  }

  // ========== Chat Helpers ==========
  function addMessage(text, role) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  }

  function addBotMessage(text) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'chat-msg bot';
    div.innerHTML = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  }

  function typeText(el, text, onDone) {
    let i = 0;
    const container = el.parentElement;
    function tick() {
      if (i < text.length) {
        let formatted = text.substring(0, i + 1);
        posts.forEach(p => {
          if (formatted.includes(p.title)) {
            formatted = formatted.replace(
              new RegExp(p.title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'),
              `<a href="post.html?id=${p.id}">${p.title}</a>`
            );
          }
        });
        el.innerHTML = formatted;
        container.scrollTop = container.scrollHeight;
        i++;
        const delay = text.charCodeAt(i - 1) > 127 ? 35 : 18;
        setTimeout(tick, delay);
      } else {
        onDone();
      }
    }
    tick();
  }

  // ========== Backend API Call (SSE Streaming) ==========
  async function chatStream(question, browserHistory, onToken, onDone, onError) {
    const sessionId = getSessionId();

    if (API_BASE) {
      // Use backend API with streaming
      try {
        const res = await fetch(`${API_BASE}/api/chat/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            message: question,
            browser_history: browserHistory,
          }),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullReply = '';
        let done = false;

        // Background reader
        (async () => {
          try {
            while (true) {
              const { done: streamDone, value } = await reader.read();
              if (streamDone) { done = true; break; }
              buffer += decoder.decode(value, { stream: true });
            }
          } catch (_) { done = true; }
        })();

        // Poll for tokens
        await new Promise((resolve) => {
          const interval = setInterval(() => {
            const nl = buffer.indexOf('\n');
            if (nl !== -1) {
              const lines = buffer.split('\n');
              buffer = lines.pop();
              for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed || !trimmed.startsWith('data:')) continue;
                const payload = trimmed.slice(5).trim();
                if (payload === '[DONE]') continue;
                try {
                  const obj = JSON.parse(payload);
                  if (obj.content) {
                    fullReply += obj.content;
                    onToken(obj.content, fullReply);
                  }
                } catch (_) {}
              }
            }
            if (done) {
              clearInterval(interval);
              onDone(fullReply);
              resolve();
            }
          }, 30);
        });
      } catch (e) {
        onError(e);
      }
    } else {
      // Fallback: direct DeepSeek call (no memory)
      onError(new Error('后端未启动。请运行 docker-compose up 启动后端服务。'));
    }
  }

  // ========== Main Chat ==========
  async function ask(question) {
    addMessage(question, 'user');
    document.getElementById('chatSuggestions').style.display = 'none';
    document.getElementById('chatInput').value = '';

    chatHistory.push({ role: 'user', content: question });

    const botDiv = addBotMessage('<em style="color:#b0a898">正在思考...</em>');

    await chatStream(
      question,
      chatHistory.slice(0, -1), // send history without current message
      (token, full) => {
        let formatted = full;
        posts.forEach(p => {
          if (formatted.includes(p.title)) {
            formatted = formatted.replace(
              new RegExp(p.title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'),
              `<a href="post.html?id=${p.id}">${p.title}</a>`
            );
          }
        });
        botDiv.innerHTML = formatted;
        const container = document.getElementById('chatMessages');
        container.scrollTop = container.scrollHeight;
      },
      (fullReply) => {
        chatHistory.push({ role: 'assistant', content: fullReply });
        // Keep browser history manageable
        if (chatHistory.length > 20) {
          chatHistory = chatHistory.slice(-12);
        }
      },
      (e) => {
        console.error('[ChatBot]', e);
        botDiv.innerHTML = '出错了: ' + e.message;
      }
    );
  }

  function send() {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;
    ask(text);
  }

  // ========== Inline Chat (post page) ==========
  let inlineHistory = [];

  function inlineAddBot(text) {
    const container = document.getElementById('inlineChatMessages');
    if (!container) return null;
    const div = document.createElement('div');
    div.className = 'chat-msg bot';
    div.innerHTML = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  }

  function inlineAddUser(text) {
    const container = document.getElementById('inlineChatMessages');
    if (!container) return;
    const div = document.createElement('div');
    div.className = 'chat-msg user';
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  async function inlineAsk(question) {
    inlineAddUser(question);
    document.getElementById('inlineChatSuggestions').style.display = 'none';
    document.getElementById('inlineChatInput').value = '';

    const postTitle = document.querySelector('.post-detail-header h1')?.textContent || '';
    const postContent = document.querySelector('.post-detail-content')?.textContent?.substring(0, 500) || '';
    inlineHistory.push({ role: 'user', content: question });

    const botDiv = inlineAddBot('<em style="color:#b0a898">正在思考...</em>');

    // For inline chat, send post context as part of the message
    const enrichedQuestion = `[关于文章「${postTitle}」] ${question}`;

    await chatStream(
      enrichedQuestion,
      inlineHistory.slice(0, -1),
      (token, full) => {
        botDiv.innerHTML = full;
        const container = document.getElementById('inlineChatMessages');
        container.scrollTop = container.scrollHeight;
      },
      (fullReply) => {
        inlineHistory.push({ role: 'assistant', content: fullReply });
        if (inlineHistory.length > 16) {
          inlineHistory = inlineHistory.slice(-10);
        }
      },
      (e) => {
        botDiv.innerHTML = '出错了: ' + e.message;
      }
    );
  }

  function inlineSend() {
    const input = document.getElementById('inlineChatInput');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;
    inlineAsk(text);
  }

  // ========== Expose ==========
  window.ChatBot = { toggle, ask, send, inlineAsk, inlineSend };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initChat);
  } else {
    initChat();
  }
})();
