import React, { useState, useEffect, useRef } from 'react';
import {
  sendChatMessage,
  fetchHealth,
  fetchAgents,
  fetchTools,
  fetchDashboardMetrics,
  fetchReadiness,
  executeMcpTool,
  fetchIssues,
  createIssue,
  updateIssue,
  deleteIssue,
} from './api';
import { useAuth } from './AuthContext';
import {
  ChatMessage,
  AgentInfo,
  ToolInfo,
  HealthInfo,
  ReadinessInfo,
  ChatResponse,
} from './types';

type Tab =
  | 'overview'
  | 'chat'
  | 'agents'
  | 'tools'
  | 'analytics'
  | 'data'
  | 'executions'
  | 'health';

const SUGGESTED_QUESTIONS = [
  'Show critical unresolved bugs.',
  'Which component has the most bugs?',
  'What is the current bug trend?',
  'Which bugs have been reopened?',
  'Which component is highest risk?',
  'Give me a complete engineering health report.',
];

const renderInlineMarkdown = (text: string) => {
  if (!text) return null;
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={idx}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={idx} className="md-code">{part.slice(1, -1)}</code>;
    }
    return part;
  });
};

const MarkdownRenderer: React.FC<{ content: string }> = ({ content }) => {
  if (!content) return null;

  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // Table rendering
    if (trimmed.startsWith('|') && trimmed.endsWith('|') && i + 1 < lines.length && lines[i + 1].trim().includes('---')) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        tableLines.push(lines[i].trim());
        i++;
      }

      if (tableLines.length >= 2) {
        const headerCells = tableLines[0].split('|').slice(1, -1).map(c => c.trim());
        const bodyRows = tableLines.slice(2).map(row => row.split('|').slice(1, -1).map(c => c.trim()));

        elements.push(
          <div key={`table-${i}`} className="md-table-wrapper">
            <table className="md-table">
              <thead>
                <tr>
                  {headerCells.map((h, hIdx) => (
                    <th key={hIdx}>{renderInlineMarkdown(h)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bodyRows.map((r, rIdx) => (
                  <tr key={rIdx}>
                    {r.map((c, cIdx) => (
                      <td key={cIdx}>{renderInlineMarkdown(c)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        continue;
      }
    }

    // Headings
    if (trimmed.startsWith('# ')) {
      elements.push(<h1 key={i} className="md-h1">{renderInlineMarkdown(trimmed.slice(2))}</h1>);
      i++;
      continue;
    }
    if (trimmed.startsWith('## ')) {
      elements.push(<h2 key={i} className="md-h2">{renderInlineMarkdown(trimmed.slice(3))}</h2>);
      i++;
      continue;
    }
    if (trimmed.startsWith('### ')) {
      elements.push(<h3 key={i} className="md-h3">{renderInlineMarkdown(trimmed.slice(4))}</h3>);
      i++;
      continue;
    }

    // Blockquote
    if (trimmed.startsWith('> ')) {
      elements.push(<blockquote key={i} className="md-blockquote">{renderInlineMarkdown(trimmed.slice(2))}</blockquote>);
      i++;
      continue;
    }

    // Bullet List
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      const listItems: string[] = [];
      while (i < lines.length && (lines[i].trim().startsWith('- ') || lines[i].trim().startsWith('* '))) {
        listItems.push(lines[i].trim().slice(2));
        i++;
      }
      elements.push(
        <ul key={`ul-${i}`} className="md-ul">
          {listItems.map((item, itemIdx) => (
            <li key={itemIdx} className="md-li">{renderInlineMarkdown(item)}</li>
          ))}
        </ul>
      );
      continue;
    }

    // Blank line
    if (!trimmed) {
      i++;
      continue;
    }

    // Paragraph
    elements.push(<p key={i} className="md-p">{renderInlineMarkdown(trimmed)}</p>);
    i++;
  }

  return <div className="markdown-rendered-content">{elements}</div>;
};

export const App: React.FC = () => {
  const { user, token: authContextToken, login, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  const userRole = (user?.role || '').toUpperCase();
  const canCreate = ['ADMIN', 'MANAGER', 'DEVELOPER', 'ENGINEER'].includes(userRole);
  const canEdit = ['ADMIN', 'MANAGER', 'DEVELOPER', 'ENGINEER'].includes(userRole);
  const canDelete = ['ADMIN', 'MANAGER'].includes(userRole);

  const handleSwitchRole = async (targetRole: string) => {
    const roleCredentials: Record<string, { email: string; pass: string }> = {
      ADMIN: { email: 'admin@acme.com', pass: 'AdminPass123!' },
      MANAGER: { email: 'manager@acme.com', pass: 'ManagerPass123!' },
      DEVELOPER: { email: 'developer@acme.com', pass: 'DeveloperPass123!' },
      VIEWER: { email: 'viewer@acme.com', pass: 'ViewerPass123!' },
    };

    const cred = roleCredentials[targetRole];
    if (cred) {
      try {
        await login(cred.email, cred.pass);
      } catch (err) {
        console.error('Failed to switch role:', err);
      }
    }
  };

  const getInitials = (name: string) => {
    if (!name) return 'BP';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  // Ground-truth state fetched from backend APIs
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [readiness, setReadiness] = useState<ReadinessInfo | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [issues, setIssues] = useState<any[]>([]);
  const [executionLogs, setExecutionLogs] = useState<ChatResponse[]>([]);
  const [selectedExecution, setSelectedExecution] = useState<ChatResponse | null>(null);

  const [isLoadingData, setIsLoadingData] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>('');

  // Issue CRUD Modal & Form State
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingIssue, setEditingIssue] = useState<any | null>(null);

  const [formTitle, setFormTitle] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formProject, setFormProject] = useState('BugPilot');
  const [formComponent, setFormComponent] = useState('Authentication');
  const [formPriority, setFormPriority] = useState('High');
  const [formSeverity, setFormSeverity] = useState('Critical');
  const [formStatus, setFormStatus] = useState('Open');
  const [formAssignee, setFormAssignee] = useState('Acme Dev');

  // Overview Filters
  const [projectFilter, setProjectFilter] = useState<string>('all');
  const [componentFilter, setComponentFilter] = useState<string>('all');

  // Dynamic lists from backend dataset
  const [availableProjects, setAvailableProjects] = useState<string[]>([]);
  const [availableComponents, setAvailableComponents] = useState<string[]>([]);

  // Interactive state
  const [toolExecutionResults, setToolExecutionResults] = useState<Record<string, any>>({});
  const [executingToolName, setExecutingToolName] = useState<string | null>(null);

  // Chat tab state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const openCreateModal = () => {
    setEditingIssue(null);
    setFormTitle('');
    setFormDescription('');
    setFormProject('BugPilot');
    setFormComponent('Authentication');
    setFormPriority('High');
    setFormSeverity('Critical');
    setFormStatus('Open');
    setFormAssignee('Acme Dev');
    setIsModalOpen(true);
  };

  const openEditModal = (issue: any) => {
    setEditingIssue(issue);
    setFormTitle(issue.title || '');
    setFormDescription(issue.description || '');
    setFormProject(issue.project || 'BugPilot');
    setFormComponent(issue.component || 'General');
    setFormPriority(issue.priority || 'Medium');
    setFormSeverity(issue.severity || 'Medium');
    setFormStatus(issue.status || 'Open');
    setFormAssignee(issue.assignee || 'Unassigned');
    setIsModalOpen(true);
  };

  const getAuthCredentials = () => {
    const token = authContextToken || localStorage.getItem('bugpilot_token') || undefined;
    const orgId = user?.org_id || localStorage.getItem('bugpilot_org_id') || 'org-acme';
    return { token, orgId };
  };

  const refreshAllData = async () => {
    setIsLoadingData(true);
    setFetchError(null);
    try {
      const { token, orgId } = getAuthCredentials();

      const [hRes, rRes, aRes, tRes, mRes, iRes] = await Promise.all([
        fetchHealth(),
        fetchReadiness().catch(() => null),
        fetchAgents(),
        fetchTools(),
        fetchDashboardMetrics(token, orgId, projectFilter, componentFilter),
        fetchIssues(token, orgId).catch(() => []),
      ]);

      setHealth(hRes);
      setReadiness(rRes);
      setAgents(aRes.agents || []);
      setTools(tRes.tools || []);
      setMetrics(mRes || null);
      setIssues(iRes || []);
      setLastUpdated(new Date().toLocaleTimeString());

      const projs: string[] = iRes.map((i: any) => String(i.project || '')).filter((p: string, idx: number, arr: string[]) => p !== '' && arr.indexOf(p) === idx);
      const comps: string[] = iRes.map((i: any) => String(i.component || '')).filter((c: string, idx: number, arr: string[]) => c !== '' && arr.indexOf(c) === idx);
      if (projs.length > 0) setAvailableProjects(projs);
      if (comps.length > 0) setAvailableComponents(comps);
    } catch (err: any) {
      setFetchError(err.message || 'Failed to connect to backend API.');
    } finally {
      setIsLoadingData(false);
    }
  };

  const handleSaveIssue = async (e: React.FormEvent) => {
    e.preventDefault();
    const { token, orgId } = getAuthCredentials();
    const payload = {
      title: formTitle,
      description: formDescription,
      project: formProject,
      component: formComponent,
      priority: formPriority,
      severity: formSeverity,
      status: formStatus,
      assignee: formAssignee,
    };
    try {
      if (editingIssue) {
        await updateIssue(editingIssue.id, payload, token, orgId);
      } else {
        await createIssue(payload, token, orgId);
      }
      setIsModalOpen(false);
      await refreshAllData();
    } catch (err: any) {
      alert(err.message || 'Failed to save issue.');
    }
  };

  const handleDeleteIssue = async (issueId: string) => {
    if (!window.confirm(`Are you sure you want to delete issue ${issueId}?`)) return;
    const { token, orgId } = getAuthCredentials();
    try {
      await deleteIssue(issueId, token, orgId);
      await refreshAllData();
    } catch (err: any) {
      alert(err.message || 'Failed to delete issue.');
    }
  };

  // Re-fetch metrics whenever projectFilter or componentFilter changes
  useEffect(() => {
    refreshAllData();
  }, [projectFilter, componentFilter]);



  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isChatLoading]);

  const handleSendChat = async (textToSend?: string) => {
    const query = textToSend || chatInput;
    if (!query.trim() || isChatLoading) return;

    setChatError(null);
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setChatInput('');
    setIsChatLoading(true);

    try {
      const response = await sendChatMessage(query);
      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        sender: 'assistant',
        text: response.answer,
        timestamp: new Date().toLocaleTimeString(),
        responseDetails: response,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setExecutionLogs((prev) => [response, ...prev]);
      if (!selectedExecution) setSelectedExecution(response);

      const { token, orgId } = getAuthCredentials();
      fetchDashboardMetrics(token, orgId, projectFilter, componentFilter).then(setMetrics).catch(console.error);
    } catch (err: any) {
      setChatError(err.message || 'Error communicating with BugPilot agent.');
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleExecuteTool = async (toolName: string) => {
    setExecutingToolName(toolName);
    const { token, orgId } = getAuthCredentials();
    const st = Date.now();
    try {
      const res = await executeMcpTool(toolName, token, orgId);
      const elapsedMs = Date.now() - st;
      setToolExecutionResults((prev) => ({
        ...prev,
        [toolName]: {
          status: 'success',
          elapsedMs,
          data: res.result,
          executedAt: new Date().toLocaleTimeString(),
        },
      }));
    } catch (err: any) {
      const elapsedMs = Date.now() - st;
      setToolExecutionResults((prev) => ({
        ...prev,
        [toolName]: {
          status: 'error',
          elapsedMs,
          error: err.message || 'Execution failed',
          executedAt: new Date().toLocaleTimeString(),
        },
      }));
    } finally {
      setExecutingToolName(null);
    }
  };



  const rawSummary = metrics?.summary || {};
  const rawTrends = metrics?.trends || [];
  const rawComponentRisks = metrics?.component_risks || [];

  // Calculate max trend count for bar scaling
  const maxTrendCount = Math.max(
    1,
    ...rawTrends.map((t: any) => Math.max(t.created || 0, t.resolved || 0))
  );

  return (
    <div className="dashboard-layout">
      {/* LEFT SIDEBAR NAVIGATION */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand-title">🛸 BugPilot</div>
          <div className="brand-subtitle">AI Engineering Bug Intelligence</div>
        </div>

        <nav className="sidebar-nav">
          <button
            className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <span className="nav-icon">📊</span> Overview
          </button>
          <button
            className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            <span className="nav-icon">💬</span> Ask BugPilot
          </button>
          <button
            className={`nav-item ${activeTab === 'agents' ? 'active' : ''}`}
            onClick={() => setActiveTab('agents')}
          >
            <span className="nav-icon">🤖</span> Agents
          </button>
          <button
            className={`nav-item ${activeTab === 'tools' ? 'active' : ''}`}
            onClick={() => setActiveTab('tools')}
          >
            <span className="nav-icon">🛠️</span> MCP Tools
          </button>
          <button
            className={`nav-item ${activeTab === 'analytics' ? 'active' : ''}`}
            onClick={() => setActiveTab('analytics')}
          >
            <span className="nav-icon">📈</span> Analytics
          </button>
          <button
            className={`nav-item ${activeTab === 'data' ? 'active' : ''}`}
            onClick={() => setActiveTab('data')}
          >
            <span className="nav-icon">🗄️</span> Data
          </button>
          <button
            className={`nav-item ${activeTab === 'executions' ? 'active' : ''}`}
            onClick={() => setActiveTab('executions')}
          >
            <span className="nav-icon">⚡</span> Executions
          </button>
          <button
            className={`nav-item ${activeTab === 'health' ? 'active' : ''}`}
            onClick={() => setActiveTab('health')}
          >
            <span className="nav-icon">🩺</span> System Health
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="synthetic-badge">
            {metrics?.data_source || health?.data_source || 'Synthetic Demo Data'}
          </div>
        </div>
      </aside>

      {/* MAIN VIEWPORT AREA */}
      <main className="main-viewport">
        {/* TOP BAR */}
        <header className="top-bar">
          <div className="top-bar-title">
            <h2>
              {activeTab === 'overview' && 'Dashboard Overview'}
              {activeTab === 'chat' && 'Ask BugPilot AI'}
              {activeTab === 'agents' && 'Specialist & Coordinator Agents'}
              {activeTab === 'tools' && 'MCP Tool Registry'}
              {activeTab === 'analytics' && 'Engineering Metrics'}
              {activeTab === 'data' && 'Provider & Data Assets'}
              {activeTab === 'executions' && 'Agentic Execution Logs'}
              {activeTab === 'health' && 'System Health & Telemetry'}
            </h2>
            {lastUpdated && (
              <span style={{ fontSize: '0.75rem', color: '#9ca3af', marginLeft: '1rem' }}>
                Updated: {lastUpdated}
              </span>
            )}
          </div>
          <div className="top-bar-status">
            {user && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginRight: '16px', fontSize: '0.825rem', color: '#94a3b8' }}>
                <div
                  style={{
                    width: '30px',
                    height: '30px',
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
                    color: '#ffffff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 700,
                    fontSize: '0.75rem',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                    letterSpacing: '0.05em',
                  }}
                >
                  {getInitials(user.full_name)}
                </div>
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{user.full_name}</span>
                <span style={{ background: 'rgba(56, 189, 248, 0.1)', color: '#38bdf8', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600 }}>
                  {user.org_id}
                </span>
                <select
                  value={userRole === 'ENGINEER' ? 'DEVELOPER' : userRole}
                  onChange={(e) => handleSwitchRole(e.target.value)}
                  style={{
                    background: 'rgba(16, 185, 129, 0.15)',
                    color: '#10b981',
                    border: '1px solid #10b981',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    outline: 'none',
                  }}
                >
                  <option value="ADMIN" style={{ background: '#1e293b', color: '#f8fafc' }}>ADMIN</option>
                  <option value="MANAGER" style={{ background: '#1e293b', color: '#f8fafc' }}>MANAGER</option>
                  <option value="DEVELOPER" style={{ background: '#1e293b', color: '#f8fafc' }}>DEVELOPER</option>
                  <option value="VIEWER" style={{ background: '#1e293b', color: '#f8fafc' }}>VIEWER</option>
                </select>
                <button
                  onClick={logout}
                  style={{
                    background: 'rgba(244, 63, 94, 0.15)',
                    border: '1px solid #f43f5e',
                    color: '#f43f5e',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                  }}
                >
                  🚪 Logout
                </button>
              </div>
            )}
            {canCreate && (
              <button
                onClick={openCreateModal}
                style={{
                  background: '#10b981',
                  color: '#fff',
                  fontWeight: 600,
                  border: 'none',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  marginRight: '12px',
                  fontSize: '0.85rem',
                }}
              >
                ➕ Create Bug
              </button>
            )}
            <span className="status-indicator online"></span>
            <span className="status-text">Backend Connected</span>
          </div>
        </header>

        {/* Global Error Banner */}
        {fetchError && (
          <div
            style={{
              padding: '12px 24px',
              background: 'rgba(244, 63, 94, 0.1)',
              borderBottom: '1px solid rgba(244, 63, 94, 0.3)',
              color: '#f43f5e',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>⚠️ {fetchError}</span>
            <button
              onClick={refreshAllData}
              style={{
                background: '#f43f5e',
                color: '#fff',
                border: 'none',
                padding: '4px 10px',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Retry Loading
            </button>
          </div>
        )}

        {/* VIEW CONTENTS */}
        <div className="view-container">
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <>
              {/* FILTERS BAR */}
              <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', background: 'rgba(255,255,255,0.03)', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid var(--border-color)', flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Project Filter:</label>
                  <select
                    value={projectFilter}
                    onChange={(e) => setProjectFilter(e.target.value)}
                    style={{ background: '#1f2937', color: '#fff', border: '1px solid #374151', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem' }}
                  >
                    <option value="all">All Active Projects</option>
                    {availableProjects.map((p, i) => (
                      <option key={i} value={p}>{p} Project</option>
                    ))}
                  </select>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Component Filter:</label>
                  <select
                    value={componentFilter}
                    onChange={(e) => setComponentFilter(e.target.value)}
                    style={{ background: '#1f2937', color: '#fff', border: '1px solid #374151', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem' }}
                  >
                    <option value="all">All Components</option>
                    {availableComponents.map((c, i) => (
                      <option key={i} value={c}>{c}</option>
                    ))}
                  </select>
                </div>

                {(projectFilter !== 'all' || componentFilter !== 'all') && (
                  <button
                    onClick={() => { setProjectFilter('all'); setComponentFilter('all'); }}
                    style={{ background: '#374151', color: '#9ca3af', border: 'none', padding: '4px 8px', borderRadius: '4px', fontSize: '0.75rem', cursor: 'pointer' }}
                  >
                    Reset Filters
                  </button>
                )}

                {isLoadingData && (
                  <span style={{ marginLeft: 'auto', color: '#38bdf8', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <div className="spinner-sm"></div> Fetching live backend metrics...
                  </span>
                )}
              </div>

              <div className="kpi-grid">
                <div className="kpi-card">
                  <span className="kpi-title">Total Bugs Analyzed</span>
                  <span className="kpi-value">{rawSummary.total_bugs !== undefined ? rawSummary.total_bugs : '—'}</span>
                  <span className="kpi-subtitle">
                    {projectFilter !== 'all' ? `Project: ${projectFilter}` : 'Across All Projects'}
                  </span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-title">Open Unresolved Bugs</span>
                  <span className="kpi-value" style={{ color: '#38bdf8' }}>
                    {rawSummary.open_bugs !== undefined ? rawSummary.open_bugs : '—'}
                  </span>
                  <span className="kpi-subtitle">Require SLA Attention</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-title">Critical & High Bugs</span>
                  <span className="kpi-value" style={{ color: '#ef4444' }}>
                    {rawSummary.critical_high_bugs !== undefined ? rawSummary.critical_high_bugs : '—'}
                  </span>
                  <span className="kpi-subtitle">High Severity Backlog</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-title">Highest Risk Component</span>
                  <span className="kpi-value" style={{ color: '#f59e0b', fontSize: '1.4rem' }}>
                    {rawComponentRisks[0]?.name || '—'}
                  </span>
                  <span className="kpi-subtitle">
                    Risk Score: {rawComponentRisks[0]?.risk_score !== undefined ? `${rawComponentRisks[0].risk_score}/100` : '—'}
                  </span>
                </div>
              </div>

              <div className="grid-2col">
                <div className="dashboard-panel">
                  <div className="panel-header">
                    <span className="panel-title">Creation vs Resolution Trends (Monthly)</span>
                  </div>
                  {rawTrends.length > 0 ? (
                    <div className="chart-container">
                      {rawTrends.slice(-6).map((t: any, idx: number) => {
                        const createdCnt = t.created !== undefined ? t.created : (t.created_count || 0);
                        const resolvedCnt = t.resolved !== undefined ? t.resolved : (t.resolved_count || 0);
                        const createdHeight = Math.max(4, Math.round((createdCnt / maxTrendCount) * 140));
                        const resolvedHeight = Math.max(4, Math.round((resolvedCnt / maxTrendCount) * 140));

                        return (
                          <div key={idx} className="chart-bar-wrapper">
                            <div className="chart-bar-group">
                              <div
                                className="bar-created"
                                style={{ height: `${createdHeight}px` }}
                                title={`Created: ${createdCnt}`}
                              />
                              <div
                                className="bar-resolved"
                                style={{ height: `${resolvedHeight}px` }}
                                title={`Resolved: ${resolvedCnt}`}
                              />
                            </div>
                            <span className="chart-label">{t.period}</span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div style={{ padding: '2rem', textAlign: 'center', color: '#9ca3af', fontSize: '0.85rem' }}>
                      No trend data available for this filter
                    </div>
                  )}
                </div>

                <div className="dashboard-panel">
                  <div className="panel-header">
                    <span className="panel-title">Top High Risk Components</span>
                  </div>
                  <div className="risk-list">
                    {rawComponentRisks.length > 0 ? (
                      rawComponentRisks.slice(0, 4).map((c: any, idx: number) => (
                        <div key={idx} className="risk-item">
                          <div className="risk-info">
                            <span className="risk-name">{c.name}</span>
                            <span className="risk-reason">
                              {c.reasons ? c.reasons.join(', ') : 'High bug concentration'}
                            </span>
                          </div>
                          <span className="risk-badge">{c.risk_score}/100</span>
                        </div>
                      ))
                    ) : (
                      <div style={{ padding: '1.5rem', textAlign: 'center', color: '#9ca3af', fontSize: '0.85rem' }}>
                        No component risk data available for this filter
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* TAB 2: ASK BUGPILOT (CHAT) */}
          {activeTab === 'chat' && (
            <div className="chat-viewport">
              <div className="chat-messages">
                {chatError && (
                  <div style={{ padding: '0.75rem 1rem', backgroundColor: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', color: '#fca5a5', borderRadius: '8px', fontSize: '0.85rem' }}>
                    ⚠️ {chatError}
                  </div>
                )}
                {messages.length === 0 && (
                  <div style={{ textAlign: 'center', color: '#9ca3af', marginTop: '2rem' }}>
                    <h3>Ask BugPilot Engineering AI</h3>
                    <p style={{ fontSize: '0.875rem', marginTop: '0.5rem' }}>
                      Select a prompt below or enter custom questions to trigger agentic tool orchestration over MCP.
                    </p>
                  </div>
                )}

                {messages.map((msg) => (
                  <div key={msg.id} className={`chat-bubble ${msg.sender}`}>
                    <div className="markdown-text">
                      <MarkdownRenderer content={msg.text} />
                    </div>
                    {msg.sender === 'assistant' && msg.responseDetails && (
                      <div className="chat-meta" style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                        <div style={{ fontSize: '0.75rem', color: '#38bdf8', marginBottom: '0.4rem', fontWeight: 600 }}>
                          ⚡ Real Execution Trace (ID: {msg.responseDetails.execution_id} | Req: {msg.responseDetails.request_id})
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', fontSize: '0.75rem', color: '#d1d5db' }}>
                          <div>1. Query Received → Orchestrator Agent initialized</div>
                          <div>2. Agents Invoked → {msg.responseDetails.agents_used.join(', ')}</div>
                          <div>3. MCP Tools Executed → {msg.responseDetails.tools_used.join(', ')}</div>
                          <div>4. Reflection Agent Audit → Verdict: <strong style={{ color: msg.responseDetails.reflection.verdict === 'CONFIRM' ? '#10b981' : '#f59e0b' }}>{msg.responseDetails.reflection.verdict}</strong> (Quality Score: {msg.responseDetails.reflection.quality_score})</div>
                          <div>5. Final Response Rendered in {msg.responseDetails.elapsed_seconds}s</div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {isChatLoading && (
                  <div className="chat-bubble assistant">
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', color: '#38bdf8' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div className="spinner-sm"></div>
                        <strong>Executing Agentic Loop...</strong>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#9ca3af', paddingLeft: '1.5rem' }}>
                        Step 1/4: Analyzing prompt & selecting specialist agents...<br />
                        Step 2/4: Invoking read-only MCP tools over stdio JSON-RPC...<br />
                        Step 3/4: Running Reflection Agent verification...
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              <div style={{ padding: '0.75rem 1.25rem', backgroundColor: '#111827', borderTop: '1px solid #374151' }}>
                <span style={{ fontSize: '0.75rem', color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase' }}>
                  Suggested Engineering Prompts
                </span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.4rem' }}>
                  {SUGGESTED_QUESTIONS.map((q, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendChat(q)}
                      disabled={isChatLoading}
                      style={{
                        backgroundColor: '#1f2937',
                        border: '1px solid #374151',
                        color: '#d1d5db',
                        padding: '0.3rem 0.6rem',
                        borderRadius: '12px',
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>

              <form
                className="chat-input-bar"
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendChat();
                }}
              >
                <input
                  type="text"
                  className="chat-input-field"
                  placeholder="Ask BugPilot about bug metrics, component risk, or sprint trends..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  disabled={isChatLoading}
                />
                <button type="submit" className="chat-send-btn" disabled={isChatLoading || !chatInput.trim()}>
                  Send Query
                </button>
              </form>
            </div>
          )}

          {/* TAB 3: AGENTS */}
          {activeTab === 'agents' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div className="dashboard-panel">
                <div className="panel-header">
                  <span className="panel-title">Active Agent Execution Telemetry</span>
                </div>
                {executionLogs.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <div style={{ color: '#38bdf8', fontSize: '0.9rem' }}>
                      Latest Execution #{executionLogs[0].execution_id} Active Agents: {' '}
                      <strong>{executionLogs[0].agents_used.join(', ')}</strong> | Tools used: {' '}
                      <strong>{executionLogs[0].tools_used.join(', ')}</strong>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                      {executionLogs[0].agents_used.map((agName, i) => (
                        <span key={i} className="risk-badge" style={{ background: 'rgba(56,189,248,0.2)', color: '#38bdf8' }}>
                          🟢 ACTIVE: {agName}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p style={{ color: '#9ca3af', fontSize: '0.85rem' }}>
                    No agent executions recorded in current session. Execute a query in Ask BugPilot to observe live agent activities.
                  </p>
                )}
              </div>

              <div className="cards-grid">
                {agents.map((a, idx) => {
                  const isRecentlyActive = executionLogs.length > 0 && executionLogs[0].agents_used.includes(a.name);
                  return (
                    <div key={idx} className="agent-card" style={{ borderColor: isRecentlyActive ? '#38bdf8' : 'var(--border-color)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span className="agent-role">{a.role}</span>
                        {isRecentlyActive && <span style={{ fontSize: '0.7rem', color: '#10b981', fontWeight: 700 }}>● EXECUTED RECENTLY</span>}
                      </div>
                      <h3 className="agent-title">{a.name}</h3>
                      <p className="agent-desc">{a.description}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 4: MCP TOOLS */}
          {activeTab === 'tools' && (
            <div className="cards-grid">
              {tools.map((t, idx) => {
                const execState = toolExecutionResults[t.name];
                return (
                  <div key={idx} className="tool-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="agent-role">READ-ONLY MCP TOOL</span>
                      <button
                        onClick={() => handleExecuteTool(t.name)}
                        disabled={executingToolName === t.name}
                        style={{
                          background: 'rgba(56, 189, 248, 0.15)',
                          border: '1px solid #38bdf8',
                          color: '#38bdf8',
                          padding: '4px 10px',
                          borderRadius: '4px',
                          fontSize: '0.75rem',
                          cursor: 'pointer',
                        }}
                      >
                        {executingToolName === t.name ? '⏳ Running...' : '▶ Execute Tool'}
                      </button>
                    </div>
                    <h3 className="agent-title" style={{ marginTop: '0.5rem' }}>{t.name}</h3>
                    <p className="agent-desc">{t.description}</p>

                    {execState && (
                      <div style={{ marginTop: '0.75rem', padding: '0.5rem', background: 'rgba(0,0,0,0.4)', border: '1px solid #374151', borderRadius: '6px', fontSize: '0.75rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', color: execState.status === 'success' ? '#10b981' : '#f43f5e' }}>
                          <strong>Status: {execState.status.toUpperCase()}</strong>
                          <span>⏱️ {execState.elapsedMs}ms</span>
                        </div>
                        <div style={{ color: '#9ca3af', marginTop: '0.25rem' }}>Executed at {execState.executedAt}</div>
                        {execState.data && (
                          <div style={{ marginTop: '0.4rem', maxHeight: '120px', overflowY: 'auto', background: '#111827', padding: '0.4rem', borderRadius: '4px' }}>
                            <pre style={{ margin: 0, fontSize: '0.7rem', color: '#38bdf8' }}>{JSON.stringify(execState.data, null, 2)}</pre>
                          </div>
                        )}
                      </div>
                    )}

                    <div className="schema-box" style={{ marginTop: '0.75rem' }}>
                      <pre>{JSON.stringify(t.input_schema, null, 2)}</pre>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* TAB 5: ANALYTICS */}
          {activeTab === 'analytics' && (
            <div className="dashboard-panel">
              <div className="panel-header">
                <span className="panel-title">Deterministic Analytics Formula Outputs</span>
              </div>
              <div className="cards-grid" style={{ marginTop: '1rem' }}>
                <div className="kpi-card">
                  <span className="kpi-title">Average Resolution Time</span>
                  <span className="kpi-value">{rawSummary.average_resolution_time_days !== undefined ? `${rawSummary.average_resolution_time_days} days` : '—'}</span>
                  <span className="kpi-subtitle">Mean Time to Resolve (MTTR)</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-title">Reopen Rate</span>
                  <span className="kpi-value">
                    {rawSummary.reopen_rate !== undefined ? `${(rawSummary.reopen_rate * 100).toFixed(1)}%` : '—'}
                  </span>
                  <span className="kpi-subtitle">{rawSummary.reopened_bugs !== undefined ? `${rawSummary.reopened_bugs} total reopened bugs` : '—'}</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-title">Open Aging Bugs (&gt;14 Days)</span>
                  <span className="kpi-value">{metrics?.aging_bugs_count !== undefined ? metrics.aging_bugs_count : '—'}</span>
                  <span className="kpi-subtitle">Exceeding SLA thresholds</span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: DATA */}
          {activeTab === 'data' && (
            <div className="dashboard-panel">
              <div className="panel-header">
                <span className="panel-title">Data Provider Specification & Control</span>
              </div>
              <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                <strong>Active Provider:</strong>
                <span className="risk-badge" style={{ background: 'rgba(16,185,129,0.2)', color: '#10b981', fontSize: '0.9rem' }}>
                  ● PostgreSQL Database (Source of Truth)
                </span>
              </div>

              <div className="kpi-grid" style={{ marginTop: '1.5rem' }}>
                <div className="kpi-card">
                  <span className="kpi-title">Data Source Engine</span>
                  <span className="kpi-value" style={{ fontSize: '1.2rem', color: '#10b981' }}>
                    POSTGRESQL
                  </span>
                  <span className="kpi-subtitle">
                    Live Relational Persistence
                  </span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-title">Available Database Issues</span>
                  <span className="kpi-value">{issues.length > 0 ? issues.length : rawSummary.total_bugs !== undefined ? rawSummary.total_bugs : '—'}</span>
                  <span className="kpi-subtitle">PostgreSQL Source of Truth</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-title">Active Projects</span>
                  <span className="kpi-value" style={{ fontSize: '1.2rem', color: '#38bdf8' }}>
                    {availableProjects.length} Projects
                  </span>
                  <span className="kpi-subtitle">Tenant Scoped</span>
                </div>
                <div className="kpi-card">
                  <span className="kpi-title">Organization Tenant ID</span>
                  <span className="kpi-value" style={{ fontSize: '1.2rem', color: '#38bdf8' }}>
                    {metrics?.org_id || 'org-acme'}
                  </span>
                  <span className="kpi-subtitle">Tenant Isolation Enforced</span>
                </div>
              </div>

              {/* Real PostgreSQL Issues Table */}
              <div className="dashboard-panel" style={{ marginTop: '1.5rem' }}>
                <div className="panel-header">
                  <span className="panel-title">PostgreSQL Persistent Issues ({issues.length})</span>
                  {canCreate && (
                    <button
                      onClick={openCreateModal}
                      style={{ background: '#10b981', color: '#fff', fontWeight: 600, border: 'none', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}
                    >
                      ➕ Add Bug
                    </button>
                  )}
                </div>
                {issues.length === 0 ? (
                  <p style={{ color: '#9ca3af', padding: '1rem 0' }}>No issues found in PostgreSQL.{canCreate ? ' Click ➕ Add Bug to create one.' : ''}</p>
                ) : (
                  <div style={{ overflowX: 'auto', marginTop: '1rem' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-color)', color: '#9ca3af' }}>
                          <th style={{ padding: '8px' }}>Key</th>
                          <th style={{ padding: '8px' }}>Title</th>
                          <th style={{ padding: '8px' }}>Status</th>
                          <th style={{ padding: '8px' }}>Severity</th>
                          <th style={{ padding: '8px' }}>Project</th>
                          <th style={{ padding: '8px' }}>Component</th>
                          <th style={{ padding: '8px' }}>Assignee</th>
                          <th style={{ padding: '8px' }}>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {issues.map((iss: any) => (
                          <tr key={iss.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                            <td style={{ padding: '8px', color: '#38bdf8', fontWeight: 600 }}>{iss.issue_key}</td>
                            <td style={{ padding: '8px', color: '#f3f4f6' }}>{iss.title}</td>
                            <td style={{ padding: '8px' }}>
                              <span style={{
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                background: iss.status === 'Resolved' || iss.status === 'Closed' ? 'rgba(16,185,129,0.2)' : 'rgba(245,158,11,0.2)',
                                color: iss.status === 'Resolved' || iss.status === 'Closed' ? '#10b981' : '#f59e0b',
                              }}>
                                {iss.status}
                              </span>
                            </td>
                            <td style={{ padding: '8px' }}>
                              <span style={{
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                background: iss.severity === 'Critical' ? 'rgba(244,63,94,0.2)' : 'rgba(56,189,248,0.2)',
                                color: iss.severity === 'Critical' ? '#f43f5e' : '#38bdf8',
                              }}>
                                {iss.severity}
                              </span>
                            </td>
                            <td style={{ padding: '8px', color: '#9ca3af' }}>{iss.project}</td>
                            <td style={{ padding: '8px', color: '#9ca3af' }}>{iss.component}</td>
                            <td style={{ padding: '8px', color: '#9ca3af' }}>{iss.assignee || 'Unassigned'}</td>
                            <td style={{ padding: '8px' }}>
                              {canEdit && (
                                <button
                                  onClick={() => openEditModal(iss)}
                                  style={{ background: 'rgba(56,189,248,0.15)', border: '1px solid #38bdf8', color: '#38bdf8', padding: '2px 8px', borderRadius: '4px', marginRight: '6px', cursor: 'pointer', fontSize: '0.75rem' }}
                                >
                                  Edit
                                </button>
                              )}
                              {canDelete && (
                                <button
                                  onClick={() => handleDeleteIssue(iss.id)}
                                  style={{ background: 'rgba(244,63,94,0.15)', border: '1px solid #f43f5e', color: '#f43f5e', padding: '2px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem' }}
                                >
                                  Delete
                                </button>
                              )}
                              {!canEdit && !canDelete && (
                                <span style={{ color: '#6b7280', fontSize: '0.75rem' }}>Read-only</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 7: EXECUTIONS */}
          {activeTab === 'executions' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
              <div className="dashboard-panel">
                <div className="panel-header">
                  <span className="panel-title">Real Execution History</span>
                </div>
                {executionLogs.length === 0 ? (
                  <p style={{ color: '#9ca3af', fontSize: '0.875rem' }}>
                    No queries executed yet in this session. Ask BugPilot a prompt to record real execution traces.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {executionLogs.map((log, idx) => (
                      <div
                        key={idx}
                        onClick={() => setSelectedExecution(log)}
                        className="risk-item"
                        style={{
                          flexDirection: 'column',
                          alignItems: 'flex-start',
                          gap: '0.4rem',
                          cursor: 'pointer',
                          border: selectedExecution?.execution_id === log.execution_id ? '1px solid #38bdf8' : '1px solid var(--border-color)',
                          background: selectedExecution?.execution_id === log.execution_id ? 'rgba(56,189,248,0.05)' : 'transparent',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                          <strong style={{ color: '#38bdf8', fontSize: '0.85rem' }}>#{log.execution_id}</strong>
                          <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>{log.elapsed_seconds}s</span>
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#d1d5db' }}>{log.answer.slice(0, 80)}...</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="dashboard-panel">
                <div className="panel-header">
                  <span className="panel-title">Execution Step Trace Details</span>
                </div>
                {selectedExecution ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
                    <div><strong style={{ color: '#9ca3af' }}>Execution ID:</strong> {selectedExecution.execution_id}</div>
                    <div><strong style={{ color: '#9ca3af' }}>Request ID:</strong> {selectedExecution.request_id}</div>
                    <div><strong style={{ color: '#9ca3af' }}>Agents Used:</strong> {selectedExecution.agents_used.join(', ')}</div>
                    <div><strong style={{ color: '#9ca3af' }}>MCP Tools Called:</strong> {selectedExecution.tools_used.join(', ')}</div>
                    <div><strong style={{ color: '#9ca3af' }}>Reflection Verdict:</strong> <span style={{ color: selectedExecution.reflection.verdict === 'CONFIRM' ? '#10b981' : '#f59e0b', fontWeight: 700 }}>{selectedExecution.reflection.verdict}</span></div>
                    <div><strong style={{ color: '#9ca3af' }}>Quality Score:</strong> {selectedExecution.reflection.quality_score}</div>
                    <div style={{ marginTop: '0.5rem', background: '#111827', padding: '0.75rem', borderRadius: '6px', border: '1px solid #374151' }}>
                      <strong style={{ color: '#38bdf8' }}>Final Answer Result:</strong>
                      <p style={{ marginTop: '0.4rem', color: '#e5e7eb', fontSize: '0.8rem', whiteSpace: 'pre-wrap' }}>{selectedExecution.answer}</p>
                    </div>
                  </div>
                ) : (
                  <p style={{ color: '#9ca3af', fontSize: '0.85rem' }}>Select an execution trace from the left to inspect step details.</p>
                )}
              </div>
            </div>
          )}

          {/* TAB 8: SYSTEM HEALTH */}
          {activeTab === 'health' && (
            <div className="dashboard-panel">
              <div className="panel-header">
                <span className="panel-title">System Health & Component Readiness Matrix</span>
              </div>
              <div className="risk-list" style={{ marginTop: '1rem' }}>
                <div className="risk-item">
                  <span>Overall Application Status</span>
                  <span style={{ color: health?.status === 'ok' ? '#10b981' : '#f59e0b', fontWeight: 700 }}>
                    {readiness?.status?.toUpperCase() || health?.status?.toUpperCase() || 'OK'}
                  </span>
                </div>
                {readiness?.components &&
                  Object.entries(readiness.components).map(([compName, comp]: [string, any], idx) => (
                    <div key={idx} className="risk-item" style={{ background: 'rgba(255,255,255,0.02)', borderRadius: '6px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <strong style={{ textTransform: 'capitalize', color: '#f9fafb' }}>{compName}</strong>
                        <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>{comp.detail}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        {comp.latency_ms !== undefined && (
                          <span style={{ fontSize: '0.75rem', color: '#38bdf8', background: 'rgba(56,189,248,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                            ⚡ {comp.latency_ms}ms
                          </span>
                        )}
                        <span className="risk-badge" style={{ background: comp.status === 'ready' ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)', color: comp.status === 'ready' ? '#10b981' : '#ef4444' }}>
                          ● {comp.status.toUpperCase()}
                        </span>
                      </div>
                    </div>
                  ))}
                <div className="risk-item">
                  <span>Last Checked Timestamp</span>
                  <span style={{ color: '#38bdf8' }}>{readiness?.timestamp || lastUpdated || 'Just now'}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Create / Edit Bug Modal */}
      {isModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.75)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1000,
        }}>
          <div style={{
            background: '#1f2937',
            border: '1px solid #374151',
            borderRadius: '8px',
            width: '90%',
            maxWidth: '560px',
            padding: '1.5rem',
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.5)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0, color: '#f3f4f6' }}>{editingIssue ? `Edit Bug (${editingIssue.issue_key})` : 'Create New Bug'}</h3>
              <button onClick={() => setIsModalOpen(false)} style={{ background: 'none', border: 'none', color: '#9ca3af', fontSize: '1.2rem', cursor: 'pointer' }}>✕</button>
            </div>
            <form onSubmit={handleSaveIssue} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>Title</label>
                <input
                  type="text"
                  required
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  placeholder="e.g. Login fails for new users"
                  style={{ width: '100%', padding: '0.5rem', background: '#111827', border: '1px solid #374151', borderRadius: '4px', color: '#fff' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>Description</label>
                <textarea
                  rows={3}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Steps to reproduce or bug details..."
                  style={{ width: '100%', padding: '0.5rem', background: '#111827', border: '1px solid #374151', borderRadius: '4px', color: '#fff' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>Project</label>
                  <input
                    type="text"
                    value={formProject}
                    onChange={(e) => setFormProject(e.target.value)}
                    style={{ width: '100%', padding: '0.5rem', background: '#111827', border: '1px solid #374151', borderRadius: '4px', color: '#fff' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>Component</label>
                  <input
                    type="text"
                    value={formComponent}
                    onChange={(e) => setFormComponent(e.target.value)}
                    style={{ width: '100%', padding: '0.5rem', background: '#111827', border: '1px solid #374151', borderRadius: '4px', color: '#fff' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>Status</label>
                  <select
                    value={formStatus}
                    onChange={(e) => setFormStatus(e.target.value)}
                    style={{ width: '100%', padding: '0.5rem', background: '#111827', border: '1px solid #374151', borderRadius: '4px', color: '#fff' }}
                  >
                    <option value="Open">Open</option>
                    <option value="In Progress">In Progress</option>
                    <option value="Resolved">Resolved</option>
                    <option value="Closed">Closed</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>Priority</label>
                  <select
                    value={formPriority}
                    onChange={(e) => setFormPriority(e.target.value)}
                    style={{ width: '100%', padding: '0.5rem', background: '#111827', border: '1px solid #374151', borderRadius: '4px', color: '#fff' }}
                  >
                    <option value="Low">Low</option>
                    <option value="Medium">Medium</option>
                    <option value="High">High</option>
                    <option value="Critical">Critical</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>Severity</label>
                  <select
                    value={formSeverity}
                    onChange={(e) => setFormSeverity(e.target.value)}
                    style={{ width: '100%', padding: '0.5rem', background: '#111827', border: '1px solid #374151', borderRadius: '4px', color: '#fff' }}
                  >
                    <option value="Low">Low</option>
                    <option value="Medium">Medium</option>
                    <option value="High">High</option>
                    <option value="Critical">Critical</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>Assignee</label>
                <input
                  type="text"
                  value={formAssignee}
                  onChange={(e) => setFormAssignee(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem', background: '#111827', border: '1px solid #374151', borderRadius: '4px', color: '#fff' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  style={{ padding: '0.5rem 1rem', background: '#374151', border: 'none', borderRadius: '4px', color: '#fff', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{ padding: '0.5rem 1rem', background: '#10b981', border: 'none', borderRadius: '4px', color: '#fff', fontWeight: 600, cursor: 'pointer' }}
                >
                  Save Bug
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
