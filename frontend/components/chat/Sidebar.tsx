'use client';
import { useState } from 'react';
import type { Conversation } from '@/lib/storage';
import { groupByDate } from '@/lib/storage';

type Props = {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
};

export function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onRename,
  collapsed,
  onToggle,
  mobileOpen,
  onMobileClose,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const groups = groupByDate(conversations);

  const cls = [
    'sidebar',
    collapsed ? 'sidebar-collapsed' : '',
    mobileOpen ? 'sidebar-mobile-open' : '',
  ].filter(Boolean).join(' ');

  return (
    <aside className={cls}>
      <div className="sidebar-top">
        <div className="brand">
          <div className="brand-mark">OI</div>
          {!collapsed && (
            <div className="brand-text">
              <div className="brand-name">Oil India</div>
              <div className="brand-sub">PQ Assistant</div>
            </div>
          )}
        </div>
        {/* Close button (mobile drawer only — hidden via CSS on desktop). */}
        <button
          className="icon-btn sidebar-mobile-close"
          onClick={onMobileClose}
          aria-label="Close history"
          title="Close"
        >
          ✕
        </button>
        {/* Desktop collapse/expand chevron (hidden via CSS on mobile). */}
        <button
          className="icon-btn sidebar-desktop-toggle"
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand' : 'Collapse'}
        >
          {collapsed ? '›' : '‹'}
        </button>
      </div>

      <button className="new-chat-btn" onClick={onNew} title="New chat (⌘K)">
        <span className="plus">+</span>
        {!collapsed && <span>New chat</span>}
      </button>

      {!collapsed && (
        <div className="convo-list">
          {conversations.length === 0 ? (
            <div className="convo-empty">No conversations yet</div>
          ) : (
            groups.map(g => (
              <div className="convo-group" key={g.label}>
                <div className="convo-group-label">{g.label}</div>
                {g.items.map(c => (
                  <ConvoItem
                    key={c.id}
                    conv={c}
                    active={c.id === activeId}
                    editing={editingId === c.id}
                    editValue={editValue}
                    onClick={() => onSelect(c.id)}
                    onStartRename={() => {
                      setEditingId(c.id);
                      setEditValue(c.title);
                    }}
                    onChangeRename={setEditValue}
                    onCommitRename={() => {
                      if (editValue.trim()) onRename(c.id, editValue.trim());
                      setEditingId(null);
                    }}
                    onCancelRename={() => setEditingId(null)}
                    onDelete={() => onDelete(c.id)}
                  />
                ))}
              </div>
            ))
          )}
        </div>
      )}
    </aside>
  );
}

function ConvoItem({
  conv,
  active,
  editing,
  editValue,
  onClick,
  onStartRename,
  onChangeRename,
  onCommitRename,
  onCancelRename,
  onDelete,
}: {
  conv: Conversation;
  active: boolean;
  editing: boolean;
  editValue: string;
  onClick: () => void;
  onStartRename: () => void;
  onChangeRename: (v: string) => void;
  onCommitRename: () => void;
  onCancelRename: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      className={`convo-item ${active ? 'convo-item-active' : ''}`}
      onClick={editing ? undefined : onClick}
    >
      {editing ? (
        <input
          className="convo-rename"
          autoFocus
          value={editValue}
          onChange={e => onChangeRename(e.target.value)}
          onBlur={onCommitRename}
          onKeyDown={e => {
            if (e.key === 'Enter') onCommitRename();
            if (e.key === 'Escape') onCancelRename();
          }}
          onClick={e => e.stopPropagation()}
        />
      ) : (
        <>
          <span className="convo-title" title={conv.title}>{conv.title}</span>
          <div className="convo-actions" onClick={e => e.stopPropagation()}>
            <button
              className="convo-action"
              title="Rename"
              onClick={onStartRename}
            >
              ✎
            </button>
            <button
              className="convo-action convo-action-danger"
              title="Delete"
              onClick={() => {
                if (confirm(`Delete "${conv.title}"?`)) onDelete();
              }}
            >
              ✕
            </button>
          </div>
        </>
      )}
    </div>
  );
}
