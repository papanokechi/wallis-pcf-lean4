const vscode = require('vscode');

/** @type {Map<string, { messages: {role:string, content:string}[], title:string, updated:number }>} */
const conversations = new Map();
let currentId = null;

function activate(context) {
  const disposable = vscode.commands.registerCommand('claude-chat.open', () => {
    const panel = vscode.window.createWebviewPanel(
      'claudeChat',
      'Claude Chat',
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: []
      }
    );
    panel.iconPath = vscode.Uri.parse('data:image/svg+xml,' + encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="16" fill="#D97B5A"/><text x="16" y="22" text-anchor="middle" font-size="18" font-weight="bold" fill="white" font-family="serif">C</text></svg>'
    ));

    panel.webview.html = getWebviewContent();

    // Handle messages from webview
    panel.webview.onDidReceiveMessage(
      async (message) => {
        switch (message.type) {
          case 'getModels':
            await handleGetModels(panel);
            break;
          case 'sendMessage':
            await handleSendMessage(panel, message);
            break;
          case 'stopStreaming':
            if (currentCts) {
              currentCts.cancel();
            }
            break;
        }
      },
      undefined,
      context.subscriptions
    );
  });

  context.subscriptions.push(disposable);
}

async function handleGetModels(panel) {
  try {
    const models = await vscode.lm.selectChatModels();
    const modelList = models.map(m => ({
      id: m.id,
      family: m.family,
      name: m.name || m.family || m.id,
      vendor: m.vendor
    }));
    panel.webview.postMessage({ type: 'models', models: modelList });
  } catch (err) {
    panel.webview.postMessage({ type: 'error', error: 'Failed to list models: ' + err.message });
  }
}

/** @type {vscode.CancellationTokenSource | null} */
let currentCts = null;

async function handleSendMessage(panel, message) {
  const { modelId, messages, systemPrompt } = message;

  // Cancel any previous request
  if (currentCts) {
    currentCts.cancel();
    currentCts.dispose();
  }
  currentCts = new vscode.CancellationTokenSource();
  const token = currentCts.token;

  try {
    // Select the requested model
    const models = await vscode.lm.selectChatModels({ id: modelId });
    if (!models.length) {
      // Try family-based selection
      const familyModels = await vscode.lm.selectChatModels({ family: modelId });
      if (!familyModels.length) {
        // Fall back to any available model
        const anyModels = await vscode.lm.selectChatModels();
        if (!anyModels.length) {
          panel.webview.postMessage({ type: 'error', error: 'No language models available. Make sure GitHub Copilot is active.' });
          return;
        }
        models.push(anyModels[0]);
      } else {
        models.push(familyModels[0]);
      }
    }

    const model = models[0];

    // Build message array for the API
    const chatMessages = [];

    // System prompt
    if (systemPrompt) {
      chatMessages.push(vscode.LanguageModelChatMessage.User(
        `[System Instructions]\n${systemPrompt}\n[End System Instructions]\n\nPlease follow the above instructions for all responses.`
      ));
    }

    // Conversation messages
    for (const msg of messages) {
      if (msg.role === 'user') {
        chatMessages.push(vscode.LanguageModelChatMessage.User(msg.content));
      } else if (msg.role === 'assistant') {
        chatMessages.push(vscode.LanguageModelChatMessage.Assistant(msg.content));
      }
    }

    // Send request  
    const response = await model.sendRequest(chatMessages, {}, token);

    // Stream the response
    let fullText = '';
    for await (const chunk of response.text) {
      if (token.isCancellationRequested) {
        panel.webview.postMessage({ type: 'streamEnd', stopped: true });
        return;
      }
      fullText += chunk;
      panel.webview.postMessage({ type: 'streamChunk', text: chunk });
    }

    panel.webview.postMessage({ type: 'streamEnd', stopped: false });

  } catch (err) {
    if (err instanceof vscode.CancellationError || token.isCancellationRequested) {
      panel.webview.postMessage({ type: 'streamEnd', stopped: true });
    } else {
      const msg = err.message || String(err);
      // Check for consent required
      if (err.code === 'NoPermissions' || msg.includes('consent')) {
        const choice = await vscode.window.showInformationMessage(
          'Claude Chat needs permission to use the language model. Allow?',
          'Allow'
        );
        if (choice === 'Allow') {
          // Retry
          await handleSendMessage(panel, message);
          return;
        }
      }
      panel.webview.postMessage({ type: 'error', error: msg });
    }
  } finally {
    if (currentCts) {
      currentCts.dispose();
      currentCts = null;
    }
  }
}

function getWebviewContent() {
  return `<!DOCTYPE html>
<html lang="en" data-mode="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
:root {
  --bg-primary: #FAFAF8;
  --bg-secondary: #F0EDE6;
  --bg-tertiary: #E6E2D9;
  --bg-input: #FFFFFF;
  --text-primary: #1A1714;
  --text-secondary: #5C554E;
  --text-tertiary: #8C847B;
  --text-placeholder: #A8A198;
  --border: #E6E2D9;
  --border-focus: #C86B3C;
  --accent: #C86B3C;
  --accent-hover: #B55E32;
  --accent-light: #FFF3EC;
  --code-bg: #1E1E1E;
  --code-header: #2D2D2D;
  --thinking-bg: #F8F5F0;
  --thinking-border: #E0D8CC;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
  --radius-xs: 6px; --radius-sm: 10px; --radius-md: 16px;
  --sidebar-w: 260px; --chat-max-w: 740px; --header-h: 52px;
  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-mono: 'SF Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace;
  --transition: 150ms ease;
}
[data-mode="dark"] {
  --bg-primary: #1E1E1E; --bg-secondary: #252526; --bg-tertiary: #2D2D2D;
  --bg-input: #3C3C3C; --text-primary: #CCCCCC; --text-secondary: #9D9D9D;
  --text-tertiary: #6E6E6E; --text-placeholder: #555;
  --border: #3C3C3C; --border-focus: #D98A5C;
  --accent: #D98A5C; --accent-hover: #E09A6C; --accent-light: #2C2218;
  --code-bg: #0F0F0F; --code-header: #1A1A1A;
  --thinking-bg: #252220; --thinking-border: #3A332A;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.3); --shadow-md: 0 4px 16px rgba(0,0,0,0.4);
}
/* Respect VS Code theme */
body.vscode-dark { --auto-theme: dark; }
body.vscode-light { --auto-theme: light; }
body.vscode-high-contrast { --auto-theme: dark; }

html { height: 100%; }
body {
  font-family: var(--font-sans); background: var(--bg-primary); color: var(--text-primary);
  height: 100%; overflow: hidden; font-size: 15px; line-height: 1.6; -webkit-font-smoothing: antialiased;
}
#app { display: flex; height: 100vh; overflow: hidden; }

/* Sidebar */
#sidebar {
  width: var(--sidebar-w); min-width: var(--sidebar-w);
  background: var(--bg-secondary); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; transition: transform var(--transition), width var(--transition); z-index: 100;
}
#sidebar.collapsed { transform: translateX(calc(-1 * var(--sidebar-w))); min-width: 0; width: 0; overflow: hidden; border: none; }
.sidebar-header { padding: 14px 14px 8px; display: flex; align-items: center; gap: 10px; }
.sidebar-logo {
  width: 28px; height: 28px; background: linear-gradient(135deg, #D97B5A, #C86B3C);
  border-radius: 8px; display: flex; align-items: center; justify-content: center;
  color: white; font-weight: 700; font-size: 15px; font-family: serif; flex-shrink: 0;
}
.sidebar-brand { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.new-chat-btn {
  margin: 6px 14px 10px; padding: 9px 14px; background: var(--bg-primary);
  border: 1px solid var(--border); border-radius: var(--radius-sm); cursor: pointer;
  font-size: 14px; color: var(--text-primary); display: flex; align-items: center; gap: 8px;
  transition: all var(--transition); font-family: var(--font-sans);
}
.new-chat-btn:hover { background: var(--bg-tertiary); }
.new-chat-btn svg { width: 16px; height: 16px; stroke: var(--text-secondary); }
.chat-list { flex: 1; overflow-y: auto; padding: 4px 8px; }
.chat-list::-webkit-scrollbar { width: 4px; }
.chat-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
.chat-list-label { padding: 6px 10px 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-tertiary); }
.chat-item {
  padding: 8px 10px; border-radius: var(--radius-xs); cursor: pointer; font-size: 13.5px;
  color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  transition: background var(--transition); position: relative; display: flex; align-items: center; gap: 6px;
}
.chat-item:hover { background: var(--bg-tertiary); color: var(--text-primary); }
.chat-item.active { background: var(--bg-tertiary); color: var(--text-primary); font-weight: 500; }
.chat-item .chat-title { flex: 1; overflow: hidden; text-overflow: ellipsis; }
.chat-item .delete-btn {
  display: none; background: none; border: none; cursor: pointer;
  color: var(--text-tertiary); padding: 2px; border-radius: 4px; flex-shrink: 0;
}
.chat-item .delete-btn:hover { color: #E55; background: rgba(200,50,50,0.1); }
.chat-item:hover .delete-btn { display: flex; }
.sidebar-footer {
  padding: 10px 14px; border-top: 1px solid var(--border); display: flex; gap: 6px;
}
.sidebar-footer button {
  flex: 1; padding: 7px; background: transparent; border: 1px solid var(--border);
  border-radius: var(--radius-xs); cursor: pointer; color: var(--text-secondary); font-size: 12px;
  display: flex; align-items: center; justify-content: center; gap: 5px;
  transition: all var(--transition); font-family: var(--font-sans);
}
.sidebar-footer button:hover { background: var(--bg-tertiary); color: var(--text-primary); }

/* Main */
#main { flex: 1; display: flex; flex-direction: column; min-width: 0; position: relative; }
#chat-header {
  height: var(--header-h); padding: 0 16px; display: flex; align-items: center; gap: 8px;
  border-bottom: 1px solid var(--border); background: var(--bg-primary); flex-shrink: 0; z-index: 10;
}
.toggle-sidebar-btn {
  background: none; border: none; cursor: pointer; color: var(--text-secondary);
  padding: 6px; border-radius: var(--radius-xs); display: flex; align-items: center; transition: all var(--transition);
}
.toggle-sidebar-btn:hover { background: var(--bg-tertiary); color: var(--text-primary); }
.model-selector { position: relative; }
.model-selector-btn {
  background: none; border: none; cursor: pointer; font-family: var(--font-sans);
  font-size: 14px; font-weight: 600; color: var(--text-primary);
  display: flex; align-items: center; gap: 5px; padding: 6px 10px;
  border-radius: var(--radius-xs); transition: background var(--transition);
}
.model-selector-btn:hover { background: var(--bg-tertiary); }
.model-selector-btn svg { width: 12px; height: 12px; color: var(--text-tertiary); }
.model-dropdown {
  display: none; position: absolute; top: 100%; left: 0; margin-top: 4px;
  background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md); min-width: 280px; z-index: 200; padding: 4px; max-height: 400px; overflow-y: auto;
}
.model-dropdown.open { display: block; }
.model-option {
  padding: 9px 12px; cursor: pointer; border-radius: var(--radius-xs); font-size: 13.5px;
  color: var(--text-secondary); transition: all var(--transition);
  display: flex; align-items: center; justify-content: space-between;
}
.model-option:hover { background: var(--bg-tertiary); color: var(--text-primary); }
.model-option.selected { color: var(--text-primary); font-weight: 500; }
.model-option .check { color: var(--accent); font-size: 15px; }
.model-option .model-name { font-size: 13.5px; }
.model-option .model-id { font-size: 11px; color: var(--text-tertiary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px; }
.header-spacer { flex: 1; }
.header-actions { display: flex; gap: 4px; }
.header-actions button {
  background: none; border: none; cursor: pointer; color: var(--text-secondary); padding: 6px;
  border-radius: var(--radius-xs); display: flex; align-items: center; transition: all var(--transition);
}
.header-actions button:hover { background: var(--bg-tertiary); color: var(--text-primary); }
.status-badge {
  font-size: 11px; padding: 3px 8px; border-radius: 10px; display: flex; align-items: center; gap: 4px;
}
.status-badge.connected { background: #1a3a1a; color: #4ade80; }
.status-badge.disconnected { background: #3a1a1a; color: #f87171; }
.status-badge .dot { width: 6px; height: 6px; border-radius: 50%; }
.status-badge.connected .dot { background: #4ade80; }
.status-badge.disconnected .dot { background: #f87171; }

/* Messages */
#messages { flex: 1; overflow-y: auto; padding: 20px 0; scroll-behavior: smooth; }
#messages::-webkit-scrollbar { width: 6px; }
#messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 6px; }
.messages-inner { max-width: var(--chat-max-w); margin: 0 auto; padding: 0 24px; }

.welcome {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 60vh; text-align: center; padding: 40px 20px;
}
.welcome-icon {
  width: 52px; height: 52px;
  background: linear-gradient(135deg, #D97B5A 0%, #C86B3C 50%, #A8522A 100%);
  border-radius: 16px; display: flex; align-items: center; justify-content: center;
  color: white; font-size: 26px; font-weight: 700; font-family: serif;
  margin-bottom: 20px; box-shadow: 0 4px 12px rgba(200,107,60,0.25);
}
.welcome h2 { font-size: 24px; font-weight: 600; color: var(--text-primary); margin-bottom: 6px; }
.welcome p { color: var(--text-tertiary); font-size: 15px; margin-bottom: 28px; }
.welcome .sub { font-size: 13px; color: var(--text-tertiary); margin-top: -18px; margin-bottom: 28px; }
.suggestions { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; max-width: 520px; width: 100%; }
.suggestion {
  padding: 14px 16px; background: var(--bg-input); border: 1px solid var(--border);
  border-radius: var(--radius-sm); cursor: pointer; text-align: left; font-size: 13.5px;
  color: var(--text-secondary); line-height: 1.4; transition: all var(--transition); font-family: var(--font-sans);
}
.suggestion:hover { border-color: var(--accent); background: var(--accent-light); color: var(--text-primary); }
.suggestion-title { font-weight: 600; color: var(--text-primary); margin-bottom: 2px; font-size: 13.5px; }

.message { padding: 16px 0; animation: fadeIn 200ms ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.message-row { display: flex; gap: 14px; align-items: flex-start; }
.message-avatar {
  width: 28px; height: 28px; border-radius: 8px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600; margin-top: 2px;
}
.message-avatar.user { background: var(--bg-tertiary); color: var(--text-secondary); }
.message-avatar.assistant { background: linear-gradient(135deg, #D97B5A, #C86B3C); color: white; font-family: serif; }
.message-content { flex: 1; min-width: 0; font-size: 15px; line-height: 1.65; }
.message-content.user-content { color: var(--text-primary); }

/* Markdown */
.message-content h1,.message-content h2,.message-content h3,.message-content h4 { margin: 16px 0 8px; font-weight: 600; line-height: 1.3; }
.message-content h1 { font-size: 22px; } .message-content h2 { font-size: 19px; } .message-content h3 { font-size: 16.5px; }
.message-content p { margin: 8px 0; } .message-content p:first-child { margin-top: 0; } .message-content p:last-child { margin-bottom: 0; }
.message-content ul, .message-content ol { margin: 8px 0; padding-left: 24px; }
.message-content li { margin: 3px 0; }
.message-content blockquote { border-left: 3px solid var(--accent); padding: 4px 16px; margin: 10px 0; color: var(--text-secondary); background: var(--thinking-bg); border-radius: 0 var(--radius-xs) var(--radius-xs) 0; }
.message-content a { color: var(--accent); text-decoration: none; }
.message-content a:hover { text-decoration: underline; }
.message-content hr { border: none; border-top: 1px solid var(--border); margin: 16px 0; }
.message-content table { border-collapse: collapse; margin: 10px 0; width: 100%; font-size: 14px; }
.message-content th, .message-content td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; }
.message-content th { background: var(--bg-secondary); font-weight: 600; }
.message-content code { background: var(--bg-tertiary); padding: 2px 6px; border-radius: 4px; font-family: var(--font-mono); font-size: 13px; }
.message-content pre {
  margin: 12px 0; border-radius: var(--radius-sm); overflow: hidden;
  background: var(--code-bg); border: 1px solid rgba(255,255,255,0.06);
}
.message-content pre code { background: none; padding: 0; border-radius: 0; color: #D4D4D4; font-size: 13px; display: block; overflow-x: auto; }
.code-header { display: flex; align-items: center; justify-content: space-between; padding: 6px 12px; background: var(--code-header); font-size: 12px; color: #999; }
.code-header .lang-label { text-transform: lowercase; }
.code-actions { display: flex; gap: 4px; }
.code-actions button {
  background: none; border: none; cursor: pointer; color: #888; font-size: 11.5px; padding: 3px 8px;
  border-radius: 4px; font-family: var(--font-sans); transition: all var(--transition); display: flex; align-items: center; gap: 4px;
}
.code-actions button:hover { color: #ccc; background: rgba(255,255,255,0.08); }
.code-body { padding: 14px 16px; overflow-x: auto; }

.streaming-cursor::after {
  content: ''; display: inline-block; width: 2px; height: 1em; background: var(--accent);
  margin-left: 2px; animation: blink 0.8s infinite; vertical-align: text-bottom;
}
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }

/* Input */
#input-area { padding: 0 24px 20px; background: var(--bg-primary); position: relative; }
.input-wrapper { max-width: var(--chat-max-w); margin: 0 auto; }
.input-box {
  background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-md);
  padding: 12px 16px; box-shadow: var(--shadow-sm); transition: border-color var(--transition), box-shadow var(--transition);
}
.input-box:focus-within { border-color: var(--border-focus); box-shadow: 0 0 0 2px rgba(200,107,60,0.12); }
.input-top { display: flex; align-items: flex-end; gap: 8px; }
#chat-input {
  flex: 1; border: none; outline: none; background: transparent; font-family: var(--font-sans);
  font-size: 15px; color: var(--text-primary); line-height: 1.5; resize: none;
  min-height: 24px; max-height: 200px; padding: 0;
}
#chat-input::placeholder { color: var(--text-placeholder); }
.input-bottom { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; padding-top: 6px; }
.input-tools { display: flex; gap: 2px; }
.input-tools button, .send-btn {
  background: none; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all var(--transition); font-family: var(--font-sans);
}
.input-tools button { color: var(--text-tertiary); padding: 5px 7px; border-radius: var(--radius-xs); font-size: 12px; gap: 4px; }
.input-tools button:hover { color: var(--text-primary); background: var(--bg-tertiary); }
.send-btn { width: 32px; height: 32px; border-radius: 50%; background: var(--accent); color: white; }
.send-btn:hover:not(:disabled) { background: var(--accent-hover); transform: scale(1.05); }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.send-btn svg { width: 16px; height: 16px; }
.stop-btn { background: var(--text-primary) !important; color: var(--bg-primary) !important; }
.stop-btn:hover { opacity: 0.85 !important; }
.input-note { text-align: center; font-size: 11.5px; color: var(--text-tertiary); margin-top: 8px; max-width: var(--chat-max-w); margin-left: auto; margin-right: auto; }

/* Artifact panel */
#artifact-panel {
  width: 0; overflow: hidden; border-left: 1px solid var(--border); background: var(--bg-primary);
  transition: width 200ms ease; display: flex; flex-direction: column; flex-shrink: 0;
}
#artifact-panel.open { width: 480px; }
.artifact-header { height: var(--header-h); padding: 0 14px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.artifact-header h3 { font-size: 14px; font-weight: 600; }
.artifact-close { background: none; border: none; cursor: pointer; color: var(--text-secondary); padding: 4px; border-radius: var(--radius-xs); }
.artifact-close:hover { color: var(--text-primary); background: var(--bg-tertiary); }
.artifact-body { flex: 1; overflow: hidden; }
.artifact-body iframe { width: 100%; height: 100%; border: none; background: white; }
.artifact-tabs { display: flex; border-bottom: 1px solid var(--border); }
.artifact-tab {
  padding: 8px 14px; font-size: 12.5px; cursor: pointer; color: var(--text-tertiary);
  border-bottom: 2px solid transparent; background: none; border-top: none; border-left: none; border-right: none;
  font-family: var(--font-sans); transition: all var(--transition);
}
.artifact-tab:hover { color: var(--text-primary); }
.artifact-tab.active { color: var(--accent); border-bottom-color: var(--accent); }

/* Settings Modal */
.modal-overlay {
  display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 500;
  align-items: center; justify-content: center; backdrop-filter: blur(4px);
}
.modal-overlay.open { display: flex; }
.modal { background: var(--bg-input); border-radius: var(--radius-md); box-shadow: 0 8px 32px rgba(0,0,0,0.2); max-width: 520px; width: 90%; max-height: 85vh; overflow-y: auto; }
.modal-header { padding: 18px 22px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border); }
.modal-header h2 { font-size: 17px; font-weight: 600; }
.modal-close { background: none; border: none; cursor: pointer; color: var(--text-secondary); padding: 4px; border-radius: var(--radius-xs); font-size: 18px; }
.modal-close:hover { color: var(--text-primary); background: var(--bg-tertiary); }
.modal-body { padding: 20px 22px; }
.form-group { margin-bottom: 18px; }
.form-group label { display: block; font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 6px; }
.form-group .hint { font-size: 12px; color: var(--text-tertiary); margin-top: 4px; }
.form-group textarea, .form-group select {
  width: 100%; padding: 9px 12px; border: 1px solid var(--border); border-radius: var(--radius-xs);
  background: var(--bg-primary); color: var(--text-primary); font-family: var(--font-sans); font-size: 14px;
  outline: none; transition: border-color var(--transition);
}
.form-group textarea:focus, .form-group select:focus { border-color: var(--border-focus); }
.form-group textarea { resize: vertical; min-height: 80px; }
.modal-footer { padding: 14px 22px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 8px; }
.btn-primary { padding: 8px 20px; background: var(--accent); color: white; border: none; border-radius: var(--radius-xs); cursor: pointer; font-size: 14px; font-weight: 500; font-family: var(--font-sans); transition: background var(--transition); }
.btn-primary:hover { background: var(--accent-hover); }
.btn-secondary { padding: 8px 20px; background: transparent; border: 1px solid var(--border); color: var(--text-primary); border-radius: var(--radius-xs); cursor: pointer; font-size: 14px; font-family: var(--font-sans); transition: all var(--transition); }
.btn-secondary:hover { background: var(--bg-tertiary); }

.toast {
  position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%) translateY(20px);
  background: #D32; color: white; padding: 10px 20px; border-radius: var(--radius-sm); font-size: 14px;
  box-shadow: var(--shadow-md); z-index: 1000; opacity: 0; transition: all 300ms ease; pointer-events: none;
}
.toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
.toast.info { background: var(--accent); }

.loading-dots { display: inline-flex; gap: 4px; align-items: center; padding: 6px 0; }
.loading-dots span { width: 6px; height: 6px; background: var(--text-tertiary); border-radius: 50%; animation: dotPulse 1.2s infinite; }
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotPulse { 0%,100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1); } }

@media (max-width: 768px) {
  #sidebar { position: fixed; left: 0; top: 0; bottom: 0; z-index: 200; }
  #sidebar.collapsed { transform: translateX(-100%); }
  .suggestions { grid-template-columns: 1fr; }
  #artifact-panel.open { width: 100%; position: fixed; inset: 0; z-index: 150; }
}
</style>
</head>
<body>
<div id="app">
  <aside id="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-logo">C</div>
      <span class="sidebar-brand">Claude</span>
    </div>
    <button class="new-chat-btn" onclick="newChat()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      New chat
    </button>
    <div class="chat-list" id="chat-list"></div>
    <div class="sidebar-footer">
      <button onclick="openSettings()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
        Settings
      </button>
      <button onclick="toggleTheme()">
        <svg id="theme-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        Theme
      </button>
    </div>
  </aside>

  <main id="main">
    <header id="chat-header">
      <button class="toggle-sidebar-btn" onclick="toggleSidebar()"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg></button>
      <div class="model-selector">
        <button class="model-selector-btn" onclick="toggleModelDropdown(event)">
          <span id="model-display">Loading models...</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <div class="model-dropdown" id="model-dropdown"></div>
      </div>
      <div class="header-spacer"></div>
      <span class="status-badge" id="status-badge"><span class="dot"></span><span id="status-text">Connecting...</span></span>
      <div class="header-actions">
        <button title="Export conversation" onclick="exportConversation()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        </button>
      </div>
    </header>
    <div id="messages"><div class="messages-inner" id="messages-inner"></div></div>
    <div id="input-area">
      <div class="input-wrapper">
        <div class="input-box">
          <div class="input-top">
            <textarea id="chat-input" rows="1" placeholder="Message Claude..." autofocus></textarea>
            <button class="send-btn" id="send-btn" onclick="sendMessage()" disabled>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
            </button>
          </div>
          <div class="input-bottom">
            <div class="input-tools">
              <button onclick="refreshModels()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
                Refresh Models
              </button>
            </div>
            <div></div>
          </div>
        </div>
        <div class="input-note">Using VS Code Language Model API — no API key required</div>
      </div>
    </div>
  </main>

  <aside id="artifact-panel">
    <div class="artifact-header"><h3 id="artifact-title">Preview</h3><button class="artifact-close" onclick="closeArtifact()">✕</button></div>
    <div class="artifact-tabs">
      <button class="artifact-tab active" data-tab="preview" onclick="switchArtifactTab('preview',this)">Preview</button>
      <button class="artifact-tab" data-tab="code" onclick="switchArtifactTab('code',this)">Code</button>
    </div>
    <div class="artifact-body" id="artifact-body"></div>
  </aside>
</div>

<div class="modal-overlay" id="settings-modal">
  <div class="modal">
    <div class="modal-header"><h2>Settings</h2><button class="modal-close" onclick="closeSettings()">✕</button></div>
    <div class="modal-body">
      <div class="form-group">
        <label for="system-prompt">System Prompt</label>
        <textarea id="system-prompt" placeholder="You are a helpful assistant..."></textarea>
        <div class="hint">Prepended to every conversation as context.</div>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn-secondary" onclick="closeSettings()">Cancel</button>
      <button class="btn-primary" onclick="saveSettings()">Save</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
const vscode = acquireVsCodeApi();

// ── State ──
let models = [];
let selectedModelId = null;
let conversations = {};
let currentId = null;
let isStreaming = false;
let streamedText = '';
let artifactCode = '';
let settings = { systemPrompt: '', theme: 'auto' };

// Persist state via VS Code
const saved = vscode.getState();
if (saved) {
  conversations = saved.conversations || {};
  currentId = saved.currentId || null;
  selectedModelId = saved.selectedModelId || null;
  settings = { ...settings, ...(saved.settings || {}) };
}

function persistState() {
  vscode.setState({ conversations, currentId, selectedModelId, settings });
}

// ── Init ──
function init() {
  detectTheme();
  renderChatList();
  if (currentId && conversations[currentId]) {
    renderMessages();
  } else {
    showWelcome();
  }
  setupInput();
  vscode.postMessage({ type: 'getModels' });
}

// ── VS Code Message Handler ──
window.addEventListener('message', event => {
  const msg = event.data;
  switch (msg.type) {
    case 'models':
      models = msg.models;
      if (!selectedModelId && models.length) {
        // Prefer Claude model
        const claude = models.find(m => m.family?.toLowerCase().includes('claude') || m.id?.toLowerCase().includes('claude'));
        selectedModelId = claude ? claude.id : models[0].id;
      }
      updateModelDisplay();
      renderModelDropdown();
      updateStatus(true);
      persistState();
      break;
    case 'streamChunk':
      handleStreamChunk(msg.text);
      break;
    case 'streamEnd':
      handleStreamEnd(msg.stopped);
      break;
    case 'error':
      handleError(msg.error);
      break;
  }
});

// ── Theme ──
function detectTheme() {
  // Detect VS Code theme
  const body = document.body;
  if (body.classList.contains('vscode-dark') || body.classList.contains('vscode-high-contrast')) {
    document.documentElement.setAttribute('data-mode', 'dark');
  } else {
    document.documentElement.setAttribute('data-mode', 'light');
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-mode');
  document.documentElement.setAttribute('data-mode', current === 'dark' ? 'light' : 'dark');
  updateThemeIcon();
}

function updateThemeIcon() {
  const icon = document.getElementById('theme-icon');
  const mode = document.documentElement.getAttribute('data-mode');
  if (mode === 'dark') {
    icon.innerHTML = '<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>';
  } else {
    icon.innerHTML = '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';
  }
}

// ── Status ──
function updateStatus(connected) {
  const badge = document.getElementById('status-badge');
  const text = document.getElementById('status-text');
  if (connected) {
    badge.className = 'status-badge connected';
    text.textContent = models.length + ' model' + (models.length !== 1 ? 's' : '') + ' available';
  } else {
    badge.className = 'status-badge disconnected';
    text.textContent = 'No models';
  }
}

// ── Sidebar ──
function toggleSidebar() { document.getElementById('sidebar').classList.toggle('collapsed'); }

function renderChatList() {
  const list = document.getElementById('chat-list');
  const convos = Object.values(conversations).sort((a, b) => b.updated - a.updated);
  if (!convos.length) {
    list.innerHTML = '<div style="padding:20px 10px;text-align:center;color:var(--text-tertiary);font-size:13px;">No conversations yet</div>';
    return;
  }
  const now = new Date();
  const groups = {};
  convos.forEach(c => {
    const diff = Math.floor((now - new Date(c.updated)) / 86400000);
    const label = diff === 0 ? 'Today' : diff === 1 ? 'Yesterday' : diff < 7 ? 'Previous 7 days' : 'Older';
    (groups[label] = groups[label] || []).push(c);
  });
  let html = '';
  for (const [label, items] of Object.entries(groups)) {
    html += '<div class="chat-list-group"><div class="chat-list-label">' + esc(label) + '</div>';
    items.forEach(c => {
      html += '<div class="chat-item' + (c.id === currentId ? ' active' : '') + '" data-id="' + c.id + '" onclick="switchChat(\\'' + c.id + '\\')">' +
        '<span class="chat-title">' + esc(c.title || 'New Chat') + '</span>' +
        '<button class="delete-btn" onclick="event.stopPropagation();deleteChat(\\'' + c.id + '\\')" title="Delete"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg></button></div>';
    });
    html += '</div>';
  }
  list.innerHTML = html;
}

function newChat() {
  const id = 'c_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6);
  conversations[id] = { id, title: '', messages: [], created: Date.now(), updated: Date.now() };
  currentId = id;
  persistState();
  renderChatList();
  showWelcome();
  document.getElementById('chat-input').focus();
}

function switchChat(id) {
  if (isStreaming) return;
  currentId = id;
  persistState();
  renderChatList();
  renderMessages();
}

function deleteChat(id) {
  delete conversations[id];
  if (currentId === id) {
    const keys = Object.keys(conversations);
    currentId = keys.length ? keys[keys.length - 1] : null;
  }
  persistState();
  renderChatList();
  if (currentId) renderMessages(); else showWelcome();
}

// ── Model Selection ──
function toggleModelDropdown(e) {
  e.stopPropagation();
  document.getElementById('model-dropdown').classList.toggle('open');
}
document.addEventListener('click', e => {
  if (!e.target.closest('.model-selector')) document.getElementById('model-dropdown').classList.remove('open');
});

function renderModelDropdown() {
  const dd = document.getElementById('model-dropdown');
  if (!models.length) {
    dd.innerHTML = '<div style="padding:12px;text-align:center;color:var(--text-tertiary);font-size:13px;">No models found.<br>Ensure GitHub Copilot is active.</div>';
    return;
  }
  dd.innerHTML = models.map(m => {
    const sel = m.id === selectedModelId;
    const name = formatModelName(m);
    return '<div class="model-option' + (sel ? ' selected' : '') + '" data-model="' + esc(m.id) + '" onclick="selectModel(this)">' +
      '<div><div class="model-name">' + esc(name) + '</div><div class="model-id">' + esc(m.id) + '</div></div>' +
      '<span class="check">' + (sel ? '✓' : '') + '</span></div>';
  }).join('');
}

function formatModelName(m) {
  if (m.name) return m.name;
  if (m.family) {
    return m.family.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  }
  return m.id;
}

function selectModel(el) {
  selectedModelId = el.dataset.model;
  updateModelDisplay();
  renderModelDropdown();
  document.getElementById('model-dropdown').classList.remove('open');
  persistState();
}

function updateModelDisplay() {
  const el = document.getElementById('model-display');
  if (!selectedModelId) { el.textContent = 'Select model'; return; }
  const m = models.find(x => x.id === selectedModelId);
  el.textContent = m ? formatModelName(m) : selectedModelId;
}

function refreshModels() {
  vscode.postMessage({ type: 'getModels' });
  showToast('Refreshing models...', 'info');
}

// ── Settings ──
function openSettings() {
  document.getElementById('system-prompt').value = settings.systemPrompt;
  document.getElementById('settings-modal').classList.add('open');
}
function closeSettings() { document.getElementById('settings-modal').classList.remove('open'); }
function saveSettings() {
  settings.systemPrompt = document.getElementById('system-prompt').value.trim();
  persistState();
  closeSettings();
  showToast('Settings saved', 'info');
}

// ── Welcome ──
function showWelcome() {
  document.getElementById('messages-inner').innerHTML =
    '<div class="welcome">' +
    '<div class="welcome-icon">C</div>' +
    '<h2>How can I help you today?</h2>' +
    '<p>Chat with Claude via VS Code</p>' +
    '<p class="sub">Using the Language Model API — no API key needed</p>' +
    '<div class="suggestions">' +
    '<button class="suggestion" onclick="useSuggestion(this)"><div class="suggestion-title">Explain a concept</div><div>Help me understand quantum computing in simple terms</div></button>' +
    '<button class="suggestion" onclick="useSuggestion(this)"><div class="suggestion-title">Write code</div><div>Create a Python function to solve the two-sum problem</div></button>' +
    '<button class="suggestion" onclick="useSuggestion(this)"><div class="suggestion-title">Analyze & reason</div><div>Compare the pros and cons of microservices vs monolith</div></button>' +
    '<button class="suggestion" onclick="useSuggestion(this)"><div class="suggestion-title">Creative writing</div><div>Write a short story about an AI discovering music</div></button>' +
    '</div></div>';
}

function useSuggestion(el) {
  document.getElementById('chat-input').value = el.querySelector('div:last-child').textContent;
  document.getElementById('chat-input').style.height = 'auto';
  updateSendBtn();
  sendMessage();
}

// ── Input ──
function setupInput() {
  const ta = document.getElementById('chat-input');
  ta.addEventListener('input', () => {
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
    updateSendBtn();
  });
  ta.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
}
function updateSendBtn() {
  document.getElementById('send-btn').disabled = !document.getElementById('chat-input').value.trim();
}

// ── Messages ──
function renderMessages() {
  const conv = conversations[currentId];
  if (!conv) return showWelcome();
  const inner = document.getElementById('messages-inner');
  inner.innerHTML = '';
  conv.messages.forEach(m => inner.appendChild(createMsgEl(m)));
  scrollToBottom();
}

function createMsgEl(msg) {
  const div = document.createElement('div');
  div.className = 'message';
  const isUser = msg.role === 'user';
  div.innerHTML =
    '<div class="message-row">' +
    '<div class="message-avatar ' + (isUser ? 'user' : 'assistant') + '">' + (isUser ? '👤' : 'C') + '</div>' +
    '<div class="message-content' + (isUser ? ' user-content' : '') + '">' +
    '<div class="message-text">' + (isUser ? esc(msg.content).replace(/\\n/g, '<br>') : renderMd(msg.content)) + '</div>' +
    '</div></div>';
  return div;
}

// ── Markdown ──
function renderMd(text) {
  if (!text) return '';
  // Minimal markdown renderer (no external deps in webview)
  let html = text;

  // Code blocks with language
  html = html.replace(/\`\`\`(\\w+)?\\n([\\s\\S]*?)\`\`\`/g, (_, lang, code) => {
    lang = lang || 'code';
    const isHtmlLang = ['html','svg','htm'].includes((lang||'').toLowerCase());
    const previewBtn = isHtmlLang ? '<button onclick="previewArtifact(this)" data-lang="' + lang + '">▶ Preview</button>' : '';
    return '<pre><div class="code-header"><span class="lang-label">' + esc(lang) + '</span><div class="code-actions">' + previewBtn + '<button onclick="copyCode(this)">Copy</button></div></div><div class="code-body"><code>' + esc(code) + '</code></div></pre>';
  });

  // Inline code
  html = html.replace(/\`([^\`]+)\`/g, '<code>$1</code>');

  // Bold
  html = html.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
  // Italic
  html = html.replace(/\\*(.+?)\\*/g, '<em>$1</em>');

  // Headers
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // Blockquote
  html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');

  // Unordered list
  html = html.replace(/^[\\-\\*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\\/li>)/gs, '<ul>$1</ul>');
  // Remove nested ul
  html = html.replace(/<\\/ul>\\s*<ul>/g, '');

  // Ordered list
  html = html.replace(/^\\d+\\. (.+)$/gm, '<li>$1</li>');

  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr>');

  // Links
  html = html.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, '<a href="$2" target="_blank">$1</a>');

  // Paragraphs (double newlines)
  html = html.replace(/\\n\\n/g, '</p><p>');
  // Single newlines
  html = html.replace(/\\n/g, '<br>');

  if (!html.startsWith('<')) html = '<p>' + html + '</p>';

  return html;
}

// ── Send Message ──
function sendMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text || isStreaming) return;

  if (!selectedModelId) {
    showToast('No model selected. Ensure GitHub Copilot is active and refresh models.');
    return;
  }

  if (!currentId || !conversations[currentId]) newChat();
  const conv = conversations[currentId];

  const userMsg = { id: 'm_' + Date.now(), role: 'user', content: text, ts: Date.now() };
  conv.messages.push(userMsg);
  if (!conv.title) conv.title = text.slice(0, 60) + (text.length > 60 ? '...' : '');
  conv.updated = Date.now();
  persistState();

  input.value = '';
  input.style.height = 'auto';
  updateSendBtn();

  const inner = document.getElementById('messages-inner');
  if (inner.querySelector('.welcome')) inner.innerHTML = '';
  inner.appendChild(createMsgEl(userMsg));
  renderChatList();

  // Add assistant placeholder
  const assistantDiv = document.createElement('div');
  assistantDiv.className = 'message';
  assistantDiv.id = 'streaming-msg';
  assistantDiv.innerHTML =
    '<div class="message-row"><div class="message-avatar assistant">C</div>' +
    '<div class="message-content"><div class="message-text"><div class="loading-dots"><span></span><span></span><span></span></div></div></div></div>';
  inner.appendChild(assistantDiv);
  scrollToBottom();

  // Start streaming
  isStreaming = true;
  streamedText = '';
  updateStreamUI(true);

  // Send to extension
  const apiMessages = conv.messages.map(m => ({ role: m.role, content: m.content }));
  vscode.postMessage({
    type: 'sendMessage',
    modelId: selectedModelId,
    messages: apiMessages,
    systemPrompt: settings.systemPrompt
  });
}

function handleStreamChunk(text) {
  streamedText += text;
  const el = document.getElementById('streaming-msg');
  if (el) {
    const textDiv = el.querySelector('.message-text');
    textDiv.innerHTML = renderMd(streamedText);
    textDiv.classList.add('streaming-cursor');
    scrollToBottom(true);
  }
}

function handleStreamEnd(stopped) {
  const el = document.getElementById('streaming-msg');
  if (el) {
    const textDiv = el.querySelector('.message-text');
    textDiv.classList.remove('streaming-cursor');
    if (stopped && !streamedText) {
      textDiv.innerHTML = '<em style="color:var(--text-tertiary)">Response stopped.</em>';
    } else {
      textDiv.innerHTML = renderMd(streamedText);
    }
    el.id = '';
  }

  const conv = conversations[currentId];
  if (conv && streamedText) {
    conv.messages.push({ id: 'm_' + Date.now(), role: 'assistant', content: streamedText, ts: Date.now() });
    conv.updated = Date.now();
  } else if (conv && !streamedText && stopped) {
    // Don't save empty stopped messages
  }

  isStreaming = false;
  streamedText = '';
  updateStreamUI(false);
  persistState();
}

function handleError(error) {
  const el = document.getElementById('streaming-msg');
  if (el) {
    el.querySelector('.message-text').innerHTML =
      '<div style="color:#D32;padding:8px 12px;background:rgba(200,50,50,0.08);border-radius:var(--radius-xs);font-size:14px;">⚠ ' + esc(error) + '</div>';
    el.id = '';
  }
  const conv = conversations[currentId];
  if (conv && conv.messages.length && conv.messages[conv.messages.length-1].role === 'user') {
    // Don't remove the user message, just show error
  }
  isStreaming = false;
  streamedText = '';
  updateStreamUI(false);
  showToast(error);
}

function updateStreamUI(streaming) {
  const btn = document.getElementById('send-btn');
  if (streaming) {
    btn.disabled = false;
    btn.classList.add('stop-btn');
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';
    btn.onclick = () => { vscode.postMessage({ type: 'stopStreaming' }); };
  } else {
    btn.classList.remove('stop-btn');
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>';
    btn.onclick = sendMessage;
    updateSendBtn();
  }
}

// ── Code/Artifact actions ──
function copyCode(btn) {
  const code = btn.closest('pre').querySelector('.code-body code').textContent;
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy', 1500);
  });
}

function previewArtifact(btn) {
  artifactCode = btn.closest('pre').querySelector('.code-body code').textContent;
  document.getElementById('artifact-panel').classList.add('open');
  document.getElementById('artifact-title').textContent = 'Preview';
  switchArtifactTab('preview', document.querySelector('.artifact-tab[data-tab="preview"]'));
}

function switchArtifactTab(tab, el) {
  document.querySelectorAll('.artifact-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  const body = document.getElementById('artifact-body');
  if (tab === 'preview') {
    body.innerHTML = '<iframe sandbox="allow-scripts"></iframe>';
    body.querySelector('iframe').srcdoc = artifactCode;
  } else {
    body.innerHTML = '<pre style="padding:16px;margin:0;height:100%;overflow:auto;background:var(--code-bg);color:#D4D4D4;font-size:13px;font-family:var(--font-mono);white-space:pre-wrap;">' + esc(artifactCode) + '</pre>';
  }
}

function closeArtifact() { document.getElementById('artifact-panel').classList.remove('open'); }

// ── Export ──
function exportConversation() {
  const conv = conversations[currentId];
  if (!conv || !conv.messages.length) { showToast('No conversation to export'); return; }
  let text = '# ' + (conv.title || 'Conversation') + '\\n\\n';
  conv.messages.forEach(m => {
    text += '**' + (m.role === 'user' ? 'You' : 'Claude') + ':** ' + m.content + '\\n\\n---\\n\\n';
  });
  const blob = new Blob([text], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = (conv.title || 'conversation').replace(/[^a-zA-Z0-9]/g, '_') + '.md';
  a.click();
  URL.revokeObjectURL(url);
}

// ── Util ──
function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function scrollToBottom(gentle) {
  const c = document.getElementById('messages');
  if (gentle) { if (c.scrollHeight - c.scrollTop - c.clientHeight < 200) c.scrollTop = c.scrollHeight; }
  else requestAnimationFrame(() => c.scrollTop = c.scrollHeight);
}
function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (type === 'info' ? ' info' : '');
  setTimeout(() => t.className = 'toast', 3000);
}

init();
<\/script>
</body>
</html>`;
}

function deactivate() {}

module.exports = { activate, deactivate };
