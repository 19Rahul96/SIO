import {
  IconLegal,
  IconRisk,
  IconFinance,
  IconDataSci,
  IconProduct,
  IconCustom,
} from './roleIcons.jsx'

const ROLES = [
  {
    id: 'legal',
    label: 'Legal Analyst',
    icon: IconLegal,
    domain: 'legal',
    blurb: 'Contracts, compliance and case research with jurisdiction-aware retrieval.',
    allowedExtensions: ['.pdf', '.docx', '.txt'],
    acceptAttr: '.pdf,.docx,.txt',
    recommendedDocTypes: ['Contracts', 'NDAs', 'Compliance reports', 'Case law'],
    questions: [
      {
        id: 'jurisdiction',
        label: 'Jurisdiction',
        type: 'select',
        options: ['US', 'EU', 'UK', 'IN', 'Other'],
      },
      {
        id: 'confidentiality',
        label: 'Confidentiality level',
        type: 'select',
        options: ['Public', 'Internal', 'Confidential'],
      },
    ],
  },
  {
    id: 'risk',
    label: 'Risk Manager',
    icon: IconRisk,
    domain: 'risk',
    blurb: 'Audit, policy and incident analysis tailored to your risk surface.',
    allowedExtensions: ['.pdf', '.docx', '.xlsx', '.csv', '.txt'],
    acceptAttr: '.pdf,.docx,.xlsx,.csv,.txt',
    recommendedDocTypes: ['Risk registers', 'Audit reports', 'Incident logs', 'Policies'],
    questions: [
      {
        id: 'risk_domain',
        label: 'Primary risk domain',
        type: 'select',
        options: ['Operational', 'Financial', 'Cyber', 'Compliance'],
      },
      { id: 'horizon', label: 'Time horizon', type: 'text', placeholder: 'e.g. next 12 months' },
    ],
  },
  {
    id: 'finance',
    label: 'Financial Advisor',
    icon: IconFinance,
    domain: 'finance',
    blurb: 'Statements, filings and market data with reporting-period framing.',
    allowedExtensions: ['.pdf', '.xlsx', '.csv', '.txt'],
    acceptAttr: '.pdf,.xlsx,.csv,.txt',
    recommendedDocTypes: ['Statements', 'Tax filings', 'Portfolio reports', 'Market data'],
    questions: [
      { id: 'period', label: 'Reporting period', type: 'text', placeholder: 'e.g. Q4 2025' },
      {
        id: 'currency',
        label: 'Currency',
        type: 'select',
        options: ['USD', 'EUR', 'GBP', 'INR', 'Other'],
      },
    ],
  },
  {
    id: 'datasci',
    label: 'Data Scientist',
    icon: IconDataSci,
    domain: 'analytics',
    blurb: 'Datasets, notebooks and research papers with task-specific framing.',
    allowedExtensions: ['.csv', '.xlsx', '.pdf', '.txt'],
    acceptAttr: '.csv,.xlsx,.pdf,.txt',
    recommendedDocTypes: ['CSV / tabular data', 'Schema docs', 'Notebooks', 'Research papers'],
    questions: [
      {
        id: 'task_type',
        label: 'Task type',
        type: 'select',
        options: ['Classification', 'Regression', 'EDA', 'NLP'],
      },
      { id: 'target', label: 'Target variable (optional)', type: 'text', placeholder: 'e.g. churn' },
    ],
  },
  {
    id: 'product',
    label: 'Product Manager',
    icon: IconProduct,
    domain: 'general',
    blurb: 'PRDs, research and roadmap docs with product-stage context.',
    allowedExtensions: ['.pdf', '.docx', '.csv', '.txt'],
    acceptAttr: '.pdf,.docx,.csv,.txt',
    recommendedDocTypes: ['PRDs', 'User research', 'Roadmaps', 'Feedback exports'],
    questions: [
      { id: 'area', label: 'Product area', type: 'text', placeholder: 'e.g. checkout' },
      {
        id: 'stage',
        label: 'Stage',
        type: 'select',
        options: ['Discovery', 'Build', 'Launch', 'Iterate'],
      },
    ],
  },
  {
    id: 'custom',
    label: 'Custom Role',
    icon: IconCustom,
    domain: 'general',
    blurb: 'Define your own role and objective — no document-type restrictions.',
    allowedExtensions: ['.pdf', '.docx', '.txt', '.csv', '.xlsx', '.xls'],
    acceptAttr: '.pdf,.docx,.txt,.csv,.xlsx,.xls',
    recommendedDocTypes: [],
    questions: [
      { id: 'role_name', label: 'Role name', type: 'text', placeholder: 'e.g. ML Researcher' },
      {
        id: 'objective',
        label: 'Primary objective',
        type: 'text',
        placeholder: 'What you want the system to help with',
      },
    ],
  },
]

export default ROLES
