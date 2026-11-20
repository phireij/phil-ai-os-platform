import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../mission-control/mission-control.mjs", import.meta.url), "utf8");
const section = (begin, end) => source.slice(source.indexOf(begin), source.indexOf(end, source.indexOf(begin)));
const row = (id, conversation_id = "first") => ({message_id: id, conversation_id, body: id,
  sender: "ceo", created_at: "2026-11-20T00:00:00Z", authority_effect: "none"});
const page = (ids, next_cursor = null, conversation_id = "first") => ({
  conversation_id, next_cursor, messages: ids.map(id => row(id, conversation_id)),
});
const reply = (data, status = 200) => ({status, ok: status === 200, json: async () => data});

function harness(capability = "keyset-v1") {
  const panel = {};
  const button = { setAttribute: (key, value) => { button[key] = value; } };
  const status = {};
  const calls = [];
  const planned = [];
  const scroll = [];
  const resets = [];
  const thread = { children: [], prepend(...rows) { this.children.unshift(...rows); } };
  const makeNode = message => ({
    id: message.message_id,
    getBoundingClientRect() {
      const top = 10 + 30 * thread.children.indexOf(this);
      return { top, bottom: top + 25 };
    },
  });
  const byId = {
    "#conversation-history": panel, "#conversation-history-more": button, "#conversation-history-status": status,
    "#conversation-thread": thread,
  };
  const context = vm.createContext({
    URLSearchParams, document: { querySelector: id => byId[id] },
    window: { innerHeight: 900, scrollBy: (...args) => scroll.push(args) },
    fetch(path, options) {
      calls.push({path, options});
      assert.ok(planned.length > 0, "unplanned request");
      return planned.shift();
    },
    renderConversationMessage: makeNode,
    renderConversationMessages(messages) { thread.children = messages.map(makeNode); },
    resetConversationView: reason => resets.push(reason),
    capability,
  });
  vm.runInContext(`
    let conversationEpoch = 1;
    let activeConversationId = "first";
    let messageHistory = null;
    let conversationSession = { message_history_pagination: capability };
    ${section("function showMessageHistory(", "function resetConversationView(")}
    ${section("async function conversationRequest(", "async function loadConversationSession(")}
    this.latest = () => loadConversationMessages(activeConversationId);
    this.earlier = loadEarlierMessages;
    this.switchConversation = () => { activeConversationId = "second"; };
    this.switchSession = () => { conversationEpoch += 1; };
  `, context);
  return { panel, button, status, calls, planned, scroll, resets, thread, context,
    ids: () => Array.from(thread.children, node => node.id) };
}

{
  const h = harness("legacy");
  h.planned.push(reply({messages: [row("latest")]}));
  await h.context.latest();
  assert.equal(h.calls[0].path, "/api/conversations/first/messages?limit=100");
  assert.deepEqual(h.ids(), ["latest"]);
}
{
  const h = harness();
  h.planned.push(reply(page(["five", "six"], "opaque?+/")));
  await h.context.latest();
  assert.equal(h.calls[0].path, "/api/conversations/first/messages?limit=100&pagination=keyset-v1");
  assert.equal(h.calls[0].options.credentials, "same-origin");
  assert.equal(h.panel.hidden, false);
  const original = h.thread.children[0];
  let finish;
  h.planned.push(new Promise(resolve => { finish = resolve; }));
  const pending = h.context.earlier();
  const concurrent = h.context.earlier();
  assert.equal(h.calls.length, 2);
  assert.equal(h.button["aria-disabled"], "true");
  assert.equal(new URL(h.calls[1].path, "http://example.invalid").searchParams.get("cursor"), "opaque?+/");
  finish(reply(page(["three", "four", "five"], "cursor-two")));
  await Promise.all([pending, concurrent]);
  assert.equal(h.thread.children[2], original);
  assert.deepEqual(h.scroll, [[0, 60]]);
  assert.deepEqual(h.ids(), ["three", "four", "five", "six"]);
  h.planned.push(reply(page(["one", "two"])));
  await h.context.earlier();
  await h.context.earlier();
  assert.deepEqual(h.ids(), ["one", "two", "three", "four", "five", "six"]);
  assert.match(h.status.textContent, /No earlier messages remain/);
  assert.equal(h.button["aria-disabled"], "true");
  assert.equal(h.panel.hidden, false);
  assert.equal(h.calls.length, 3);
}
for (const stale of ["session", "conversation"]) {
  for (const status of [200, 401]) {
    const h = harness();
    h.planned.push(reply(page(["latest"], "cursor")));
    await h.context.latest();
    let finish;
    h.planned.push(new Promise(resolve => { finish = resolve; }));
    const pending = h.context.earlier();
    if (stale === "session") h.context.switchSession();
    else h.context.switchConversation();
    finish(reply(page(["too-late"]), status));
    await pending;
    assert.deepEqual(h.ids(), ["latest"]);
    assert.deepEqual(h.resets, []);
  }
}
for (const bad of [
  page(["one"], "initial"),
  page(["one", "one"]),
  page(["one"], null, "other-conversation"),
  page([], "new-cursor"),
  { ...page(["one"]), messages: [{...row("one"), authority_effect: "untrusted"}] },
]) {
  const h = harness();
  h.planned.push(reply(page(["latest"], "initial")), reply(bad));
  await h.context.latest();
  await h.context.earlier();
  assert.deepEqual(h.ids(), ["latest"]);
  assert.equal(h.button["aria-disabled"], "false");
  assert.match(h.status.textContent, /Try again/);
}
{
  const h = harness();
  h.planned.push(reply(page(["latest"], "expired")), reply({error: "invalid_cursor"}, 400), reply(page(["new-latest"])));
  await h.context.latest();
  await h.context.earlier();
  assert.equal(h.button.textContent, "Refresh latest messages");
  assert.deepEqual(h.ids(), ["latest"]);
  await h.context.earlier();
  assert.deepEqual(h.ids(), ["new-latest"]);
  assert.match(h.status.textContent, /No earlier messages remain/);
  assert.equal(h.panel.hidden, false);
}
console.log("Mission Control earlier-history UI contract: GREEN (legacy, prepend, exhaustion, stale status, malformed pages, cursor recovery).");
