// src/pages/TopicStudio.jsx
// Manage Topics, Tones, Custom AI Contexts and Prompt Instructions

import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { Plus, Edit2, Trash2, Check, Sparkles, Folder, Music2, ToggleLeft, ToggleRight } from 'lucide-react'

export default function TopicStudio() {
  const [activeTab, setActiveTab] = useState('topics') // 'topics' | 'tones'
  const [topics, setTopics] = useState([])
  const [tones, setTones] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingItem, setEditingItem] = useState(null) // null or item object
  const [isNew, setIsNew] = useState(false)

  // Form State
  const [formState, setFormState] = useState({
    name: '',
    description: '',
    custom_context: '',
    category: 'tech',
    render_style: '',
    is_active: true
  })

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    const [topicsRes, tonesRes] = await Promise.all([
      supabase.from('topics').select('*').order('created_at', { ascending: false }),
      supabase.from('tones').select('*').order('created_at', { ascending: false })
    ])
    if (topicsRes.data) setTopics(topicsRes.data)
    if (tonesRes.data) setTones(tonesRes.data)
    setLoading(false)
  }

  function openCreate() {
    setIsNew(true)
    setFormState({
      name: '',
      description: '',
      custom_context: '',
      category: 'tech',
      render_style: '',
      is_active: true
    })
    setEditingItem(true)
  }

  function openEdit(item) {
    setIsNew(false)
    setFormState({
      name: item.name || '',
      description: item.description || '',
      custom_context: item.custom_context || '',
      category: item.category || 'tech',
      render_style: item.render_style || '',
      is_active: item.is_active ?? true
    })
    setEditingItem(item)
  }

  async function handleSave(e) {
    e.preventDefault()
    const table = activeTab === 'topics' ? 'topics' : 'tones'
    
    const payload = {
      name: formState.name,
      description: formState.description,
      is_active: formState.is_active,
      updated_at: new Date().toISOString()
    }

    if (activeTab === 'topics') {
      payload.custom_context = formState.custom_context
      payload.category = formState.category
      payload.render_style = formState.render_style || null
    }

    if (isNew) {
      const { data, error } = await supabase.from(table).insert(payload).select()
      if (error) {
        alert(`Error adding: ${error.message}`)
      } else {
        if (activeTab === 'topics') setTopics([data[0], ...topics])
        else setTones([data[0], ...tones])
        setEditingItem(null)
      }
    } else {
      const { error } = await supabase.from(table).update(payload).eq('id', editingItem.id)
      if (error) {
        alert(`Error updating: ${error.message}`)
      } else {
        if (activeTab === 'topics') {
          setTopics(topics.map(t => t.id === editingItem.id ? { ...t, ...payload } : t))
        } else {
          setTones(tones.map(t => t.id === editingItem.id ? { ...t, ...payload } : t))
        }
        setEditingItem(null)
      }
    }
  }

  async function toggleActive(item) {
    const table = activeTab === 'topics' ? 'topics' : 'tones'
    const newStatus = !item.is_active
    const { error } = await supabase.from(table).update({ is_active: newStatus }).eq('id', item.id)
    if (!error) {
      if (activeTab === 'topics') {
        setTopics(topics.map(t => t.id === item.id ? { ...t, is_active: newStatus } : t))
      } else {
        setTones(tones.map(t => t.id === item.id ? { ...t, is_active: newStatus } : t))
      }
    }
  }

  async function handleDelete(id) {
    const table = activeTab === 'topics' ? 'topics' : 'tones'
    if (!confirm(`Are you sure you want to delete this ${activeTab === 'topics' ? 'topic' : 'tone'}?`)) return

    const { error } = await supabase.from(table).delete().eq('id', id)
    if (error) {
      alert(`Error deleting: ${error.message}`)
    } else {
      if (activeTab === 'topics') setTopics(topics.filter(t => t.id !== id))
      else setTones(tones.filter(t => t.id !== id))
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div>
          <h1>Topic & Tone Studio</h1>
          <p>Customize what topics Gemini writes about, what tones it adopts, and tailor exact prompting instructions.</p>
        </div>
        <button className="btn btn-primary" onClick={openCreate}>
          <Plus size={16} /> Add New {activeTab === 'topics' ? 'Topic' : 'Tone'}
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button
          onClick={() => { setActiveTab('topics'); setEditingItem(null) }}
          className={`btn btn-sm ${activeTab === 'topics' ? 'btn-primary' : 'btn-ghost'}`}
        >
          <Folder size={15} /> Topics ({topics.length})
        </button>
        <button
          onClick={() => { setActiveTab('tones'); setEditingItem(null) }}
          className={`btn btn-sm ${activeTab === 'tones' ? 'btn-primary' : 'btn-ghost'}`}
        >
          <Sparkles size={15} /> Tones & Styles ({tones.length})
        </button>
      </div>

      {/* Modal / Form for Create / Edit */}
      {editingItem && (
        <div className="card" style={{ marginBottom: 24, border: '1px solid var(--accent-primary)', background: 'var(--bg-elevated)' }}>
          <div className="card-header">
            <span className="card-title">
              {isNew ? `Create New ${activeTab === 'topics' ? 'Topic' : 'Tone'}` : `Edit: ${formState.name}`}
            </span>
            <button className="btn btn-ghost btn-sm" onClick={() => setEditingItem(null)}>Cancel</button>
          </div>

          <form onSubmit={handleSave}>
            <div style={{ display: 'grid', gridTemplateColumns: activeTab === 'topics' ? '1fr 200px' : '1fr', gap: 16 }}>
              <div className="form-group">
                <label className="form-label">Name</label>
                <input 
                  type="text" 
                  className="form-input" 
                  required
                  placeholder={activeTab === 'topics' ? 'e.g. How Cloud Data Centers Work' : 'e.g. Mind-Blowing Facts'}
                  value={formState.name}
                  onChange={e => setFormState({ ...formState, name: e.target.value })}
                />
              </div>

              {activeTab === 'topics' && (
                <div className="form-group">
                  <label className="form-label">Category</label>
                  <select 
                    className="form-select"
                    value={formState.category}
                    onChange={e => setFormState({ ...formState, category: e.target.value })}
                  >
                    <option value="tech">Technology / Engineering</option>
                    <option value="education">Education / Science</option>
                    <option value="lifestyle">Lifestyle / Advice</option>
                    <option value="sarcasm">Sarcasm / Comedy</option>
                  </select>
                </div>
              )}

              {activeTab === 'topics' && (
                <div className="form-group">
                  <label className="form-label">Visual Style</label>
                  <select
                    className="form-select"
                    value={formState.render_style}
                    onChange={e => setFormState({ ...formState, render_style: e.target.value })}
                  >
                    <option value="">Use global default (Settings page)</option>
                    <option value="stock_footage">Stock Footage</option>
                    <option value="whiteboard_sketch">Whiteboard Sketch</option>
                    <option value="quote_card">Quote Card</option>
                  </select>
                  <div className="form-hint">Videos generated for this topic always use this style, overriding the default.</div>
                </div>
              )}
            </div>

            <div className="form-group">
              <label className="form-label">AI Description / Core Prompt</label>
              <textarea 
                className="form-textarea"
                required
                rows={3}
                placeholder={activeTab === 'topics' 
                  ? 'Detailed explanation of what aspects of the topic the AI should cover...'
                  : 'How the AI should write in this tone (e.g., confident, punchy, witty, dramatic)...'}
                value={formState.description}
                onChange={e => setFormState({ ...formState, description: e.target.value })}
              />
              <div className="form-hint">This is passed directly to Google Gemini as the topic context.</div>
            </div>

            {activeTab === 'topics' && (
              <div className="form-group">
                <label className="form-label">Custom Admin Context & Hook Rules (Optional)</label>
                <textarea 
                  className="form-textarea"
                  rows={2}
                  placeholder="e.g. Focus on specific numbers, compare transistor size to DNA, start with a 3-second shocking hook."
                  value={formState.custom_context}
                  onChange={e => setFormState({ ...formState, custom_context: e.target.value })}
                />
                <div className="form-hint">Extra guardrails and specific analogies you want the AI to include.</div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                <input 
                  type="checkbox" 
                  checked={formState.is_active}
                  onChange={e => setFormState({ ...formState, is_active: e.target.checked })}
                />
                <span style={{ fontSize: '0.875rem' }}>Active (Include in daily generation pool)</span>
              </label>

              <div className="flex gap-2">
                <button type="button" className="btn btn-ghost" onClick={() => setEditingItem(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary">
                  <Check size={16} /> Save {activeTab === 'topics' ? 'Topic' : 'Tone'}
                </button>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* List */}
      {loading ? (
        <div className="loading-screen">
          <div className="spinner" />
          <span>Loading studio...</span>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
          {(activeTab === 'topics' ? topics : tones).map(item => (
            <div 
              key={item.id} 
              className="card"
              style={{ 
                opacity: item.is_active ? 1 : 0.6,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between'
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>
                    {item.name}
                  </h3>
                  <div className="flex gap-2">
                    {item.category && (
                      <span className="badge" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                        {item.category}
                      </span>
                    )}
                    {item.render_style && (
                      <span className="badge" style={{ background: 'var(--bg-elevated)', color: 'var(--accent-purple)' }}>
                        🎨 {item.render_style.replace(/_/g, ' ')}
                      </span>
                    )}
                    <span className={`badge badge-${item.is_active ? 'approved' : 'rejected'}`}>
                      {item.is_active ? 'Active' : 'Paused'}
                    </span>
                  </div>
                </div>

                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 12, lineHeight: 1.5 }}>
                  {item.description}
                </p>

                {item.custom_context && (
                  <div style={{ 
                    background: 'var(--bg-elevated)', 
                    padding: '8px 12px', 
                    borderRadius: 6,
                    fontSize: '0.78rem',
                    color: 'var(--accent-primary)',
                    marginBottom: 16
                  }}>
                    💡 <strong>Context:</strong> {item.custom_context}
                  </div>
                )}
              </div>

              {/* Card Footer Actions */}
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center', 
                borderTop: '1px solid var(--border)',
                paddingTop: 12,
                marginTop: 12
              }}>
                <button 
                  className="btn btn-ghost btn-sm"
                  onClick={() => toggleActive(item)}
                >
                  {item.is_active ? 'Pause' : 'Activate'}
                </button>

                <div className="flex gap-2">
                  <button className="btn btn-ghost btn-icon btn-sm" onClick={() => openEdit(item)} title="Edit">
                    <Edit2 size={14} />
                  </button>
                  <button className="btn btn-ghost btn-icon btn-sm text-danger" onClick={() => handleDelete(item.id)} title="Delete">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
