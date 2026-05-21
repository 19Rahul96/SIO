import { create } from 'zustand'

const useStore = create((set) => ({
  currentStep: 1,
  sessionStartedAt: Date.now() / 1000,
  fileStatuses: [],
  uploadedFileIds: [],
  prompt: '',
  slmResult: null,
  modelRecommendations: [],
  selectedModel: null,
  decisionData: null,
  finalRunResult: null,
  dashboardStats: null,
  qualityMetrics: null,
  wikiPages: [],
  mlMetrics: null,
  selectedWikiPage: null,
  wikiReviews: [],
  wikiLoading: false,
  wikiReviewUpdating: false,
  isAnalysing: false,
  isRunning: false,
  error: null,

  injectMode: 'selector',
  selectedRole: null,
  roleAnswers: {},
  roleStage: 'pick',

  setStep: (step) => set({ currentStep: step }),
  setPrompt: (prompt) => set({ prompt }),

  setInjectMode: (m) => set({ injectMode: m }),
  setSelectedRole: (role) => set({ selectedRole: role, roleAnswers: {}, roleStage: role ? 'questions' : 'pick' }),
  setRoleAnswer: (qid, value) =>
    set((state) => ({ roleAnswers: { ...state.roleAnswers, [qid]: value } })),
  setRoleStage: (stage) => set({ roleStage: stage }),
  resetInjectMode: () =>
    set({ injectMode: 'selector', selectedRole: null, roleAnswers: {}, roleStage: 'pick' }),

  setFileStatuses: (fileStatuses) => set({ fileStatuses }),

  addFile: (status) =>
    set((state) => ({
      fileStatuses: [
        status,
        ...state.fileStatuses.filter((s) => s.file_id !== status.file_id),
      ],
      uploadedFileIds: [...new Set([...state.uploadedFileIds, status.file_id])],
    })),

  updateFile: (fileId, updates) =>
    set((state) => ({
      fileStatuses: state.fileStatuses.map((s) =>
        s.file_id === fileId ? { ...s, ...updates } : s
      ),
    })),

  setAnalyseResult: (result) =>
    set({
      slmResult: result?.slm_result ?? null,
      modelRecommendations: result?.model_recommendations ?? [],
      decisionData: result?.decision ?? null,
      selectedModel: result?.model_recommendations?.[0]?.model?.id ?? null,
    }),

  setSelectedModel: (model) => set({ selectedModel: model }),
  setFinalRunResult: (result) => set({ finalRunResult: result }),
  setDashboardStats: (stats) => set({ dashboardStats: stats }),
  setQualityMetrics: (qualityMetrics) => set({ qualityMetrics }),
  setMlMetrics: (mlMetrics) => set({ mlMetrics }),
  setWikiPages: (wikiPages) => set({ wikiPages }),
  setSelectedWikiPage: (selectedWikiPage) => set({ selectedWikiPage }),
  setWikiReviews: (wikiReviews) => set({ wikiReviews }),
  setWikiLoading: (wikiLoading) => set({ wikiLoading }),
  setWikiReviewUpdating: (wikiReviewUpdating) => set({ wikiReviewUpdating }),
  setAnalysing: (v) => set({ isAnalysing: v }),
  setRunning: (v) => set({ isRunning: v }),
  setError: (error) => set({ error }),

  startNewSession: () =>
    set({
      currentStep: 1,
      sessionStartedAt: Date.now() / 1000,
      fileStatuses: [],
      uploadedFileIds: [],
      prompt: '',
      slmResult: null,
      modelRecommendations: [],
      selectedModel: null,
      decisionData: null,
      finalRunResult: null,
      qualityMetrics: null,
      wikiPages: [],
      selectedWikiPage: null,
      wikiReviews: [],
      wikiLoading: false,
      wikiReviewUpdating: false,
      isAnalysing: false,
      isRunning: false,
      error: null,
      injectMode: 'selector',
      selectedRole: null,
      roleAnswers: {},
      roleStage: 'pick',
    }),
}))

export default useStore
