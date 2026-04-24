export type TaskStage =
  | '上传中'
  | '待运行'
  | 'MineU解析中'
  | 'MineU解析失败'
  | '边界识别中'
  | '边界识别失败'
  | '切题匹配中'
  | '切题匹配失败'
  | '系统异常'
  | '待人工审核'
  | '已完成'

export type TaskListItem = {
  id: string
  paperId: number | null
  title: string
  stage: TaskStage
  progress: number
  hasAnswer: boolean
  mineuSuccess: boolean
  questionCount: number
  pendingReviewCount: number
  updatedAt: string | null
  errorSummary: string | null
  note: string | null
  sourceLabel: string
  isTransient?: boolean
}

export type PaperLike = {
  id: number
  title: string
  status?: string
  updated_at?: string
  answer_sheet?: {
    has_answer?: boolean
  }
  conversion_jobs?: Array<{
    status?: string
    error_message?: string | null
    job_type?: string
    updated_at?: string
  }>
  questions?: Array<unknown>
  pending_review_count?: number
}

export const STAGE_ORDER: Record<TaskStage, number> = {
  上传中: 0,
  MineU解析中: 1,
  边界识别中: 2,
  切题匹配中: 3,
  MineU解析失败: 4,
  边界识别失败: 5,
  切题匹配失败: 6,
  系统异常: 7,
  待人工审核: 8,
  待运行: 9,
  已完成: 10
}

export const stageTagType = (stage: TaskStage) => {
  switch (stage) {
    case '已完成':
      return 'success'
    case '待人工审核':
      return 'warning'
    case '边界识别中':
    case '待运行':
      return 'info'
    case 'MineU解析中':
    case '切题匹配中':
    case '上传中':
      return 'primary'
    case 'MineU解析失败':
    case '切题匹配失败':
    case '系统异常':
      return 'danger'
    default:
      return 'info'
  }
}

const jobByType = (paper: PaperLike, jobType: string) =>
  (paper.conversion_jobs || [])
    .filter((job) => job.job_type === jobType)
    .sort((a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime())[0]

export const deriveTaskFromPaper = (paper: PaperLike): TaskListItem => {
  const jobs = paper.conversion_jobs || []
  const hasAnswer = Boolean(paper.answer_sheet?.has_answer)
  const questionCount = paper.questions?.length || 0
  const pendingReviewCount = paper.pending_review_count || 0
  const paperStatus = paper.status || 'RAW'

  const paperJob = jobByType(paper, 'PAPER')
  const answerJob = jobByType(paper, 'ANSWER')
  const boundaryJob = jobByType(paper, 'BOUNDARY')
  const matchJob = jobByType(paper, 'MATCH')
  const mineuSuccess = [paperJob, answerJob].some((job) => job?.status === 'SUCCESS')

  let stage: TaskStage = '待运行'
  let progress = 8
  let errorSummary: string | null = null
  let note: string | null = null

  if (paperStatus === 'SYSTEM_FAILED') {
    stage = '系统异常'
    progress = 100
    errorSummary = matchJob?.error_message || '系统在写库或状态更新时失败，请查看日志后重新手动触发。'
    note = '建议先确认数据库与后端状态，再点击“重新运行”。'
  } else if (paperStatus === 'MINEU_FAILED' || paperJob?.status === 'FAILED' || answerJob?.status === 'FAILED') {
    stage = 'MineU解析失败'
    progress = 100
    errorSummary = paperJob?.error_message || answerJob?.error_message || 'MineU 解析失败。'
    note = '请检查原始 PDF 与 MineU 配置后，重新手动触发流程。'
  } else if (paperStatus === 'BOUNDARY_FAILED' || boundaryJob?.status === 'FAILED') {
    stage = '边界识别失败'
    progress = 100
    errorSummary = boundaryJob?.error_message || 'LLM 边界识别失败。'
    note = '请检查 MineU 产物质量与 LLM 返回内容后，重新手动触发流程。'
  } else if (paperStatus === 'MATCH_FAILED' || matchJob?.status === 'FAILED') {
    stage = '切题匹配失败'
    progress = 100
    errorSummary = matchJob?.error_message || '切题或答案匹配失败。'
    note = '请查看错误信息并重新手动触发流程。'
  } else if (paperJob?.status === 'RUNNING' || answerJob?.status === 'RUNNING') {
    stage = 'MineU解析中'
    progress = 40
    note = hasAnswer ? '正在执行试卷与答案的 MineU 解析。' : '正在执行试卷的 MineU 解析。'
  } else if (boundaryJob?.status === 'RUNNING' || paperStatus === 'BOUNDARY_RUNNING') {
    stage = '边界识别中'
    progress = 58
    note = '正在识别整卷题目与答案边界，请等待。'
  } else if (matchJob?.status === 'RUNNING' || paperStatus === 'MATCH_RUNNING') {
    stage = '切题匹配中'
    progress = 72
    note = '正在按边界切题并做全局答案匹配，请等待任务完成。'
  } else if (paperStatus === 'RAW') {
    stage = '待运行'
    progress = 8
    note = hasAnswer ? '文件已上传，尚未开始执行 MineU 解析。' : '文件已上传，但缺失答案；如需完整匹配，请先补答案后手动运行。'
  } else if (paperStatus === 'MINEU_DONE') {
    stage = '待运行'
    progress = 52
    note = 'MineU 已完成，但尚未进入 LLM 边界识别。'
  } else if (paperStatus === 'REVIEW_PENDING') {
    if (pendingReviewCount > 0) {
      stage = '待人工审核'
      progress = 92
      note = `当前有 ${pendingReviewCount} 道题需要人工确认。`
    } else {
      stage = '已完成'
      progress = 100
      note = questionCount ? `已生成 ${questionCount} 道题，待审核项已全部处理。` : '流程已完成。'
    }
  } else if (paperStatus === 'SLICED' || paperStatus === 'REVIEWED' || paperStatus === 'ARCHIVED') {
    stage = '已完成'
    progress = 100
    note = questionCount ? `已生成 ${questionCount} 道题，可继续审核或使用。` : '流程已完成。'
  }

  if (!errorSummary) {
    if (matchJob?.error_message && (stage === '待人工审核' || stage === '已完成')) {
      note = matchJob.error_message
    } else if (boundaryJob?.error_message && (stage === '边界识别中' || stage === '切题匹配中' || stage === '待人工审核' || stage === '已完成')) {
      note = boundaryJob.error_message
    }
  }

  return {
    id: `paper-${paper.id}`,
    paperId: paper.id,
    title: paper.title || `试卷 #${paper.id}`,
    stage,
    progress,
    hasAnswer,
    mineuSuccess,
    questionCount,
    pendingReviewCount,
    updatedAt: latestUpdatedAt(paper),
    errorSummary,
    note,
    sourceLabel: '试卷任务'
  }
}

export const sortTaskItems = (items: TaskListItem[]) => {
  return [...items].sort((a, b) => {
    const stageDelta = STAGE_ORDER[a.stage] - STAGE_ORDER[b.stage]
    if (stageDelta !== 0) return stageDelta
    return new Date(b.updatedAt || 0).getTime() - new Date(a.updatedAt || 0).getTime()
  })
}

export const summarizeTasks = (items: TaskListItem[]) => {
  return {
    total: items.length,
    queued: items.filter((item) => item.stage === '待运行').length,
    processing: items.filter((item) => ['上传中', 'MineU解析中', '边界识别中', '切题匹配中'].includes(item.stage)).length,
    completed: items.filter((item) => item.stage === '已完成').length,
    failed: items.filter((item) => ['MineU解析失败', '边界识别失败', '切题匹配失败', '系统异常'].includes(item.stage)).length,
    review: items.filter((item) => item.stage === '待人工审核').length
  }
}

const latestUpdatedAt = (paper: PaperLike) => {
  const timestamps = [paper.updated_at, ...(paper.conversion_jobs || []).map((job) => job.updated_at)].filter(Boolean) as string[]
  if (!timestamps.length) return null
  return timestamps.sort().at(-1) || null
}
