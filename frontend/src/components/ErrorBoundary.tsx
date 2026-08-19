import { Component, type ErrorInfo, type ReactNode } from 'react'
import { buildReportIssueUrl } from '../utils/githubIssueUrl'

type Props = {
  children: ReactNode
}

type State = {
  error: Error | null
  componentStack: string | null
}

function reportUrl(error: Error, componentStack: string | null): string {
  const title = `앱 크래시: ${error.message}`.slice(0, 200)
  const body = [
    '<!-- 아래 내용을 확인하고, 재현 방법(무엇을 하다가 발생했는지)을 위에 적어주세요. -->',
    '',
    '### 오류 메시지',
    '```',
    error.message,
    '```',
    error.stack ? `### 스택\n\`\`\`\n${error.stack.slice(0, 2000)}\n\`\`\`` : '',
    componentStack ? `### 컴포넌트 스택\n\`\`\`\n${componentStack.slice(0, 2000)}\n\`\`\`` : '',
  ]
    .filter(Boolean)
    .join('\n')
  return buildReportIssueUrl(title, body)
}

// React error boundaries must be class components - there is no hooks
// equivalent (as of React 19). This only catches errors thrown during
// rendering/lifecycle of its children, not errors in event handlers or
// async code - see useGlobalErrorToasts for those.
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, componentStack: null }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error }
  }

  componentDidCatch(_error: Error, info: ErrorInfo) {
    this.setState({ componentStack: info.componentStack ?? null })
  }

  render() {
    const { error, componentStack } = this.state
    if (!error) return this.props.children

    return (
      <div className="error-boundary">
        <h1>예상치 못한 오류가 발생했습니다</h1>
        <p>화면을 새로고침해도 반복되면 아래 버튼으로 신고해 주세요.</p>
        <div className="error-boundary-actions">
          <a
            className="error-boundary-report-link"
            href={reportUrl(error, componentStack)}
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub Issue로 신고하기
          </a>
        </div>
        <details className="error-boundary-details">
          <summary>오류 상세 (신고 시 자동으로 포함됩니다)</summary>
          <pre>{error.message}</pre>
        </details>
      </div>
    )
  }
}
