import { Link } from 'react-router-dom'

const FOOTER_GROUPS: { label: string; links: { to: string; label: string }[] }[] = [
  {
    label: '법적 문서',
    links: [
      { to: '/terms', label: '이용약관' },
      { to: '/privacy', label: '개인정보처리방침' },
      { to: '/refund', label: '환불 안내' },
    ],
  },
  {
    label: '회사 · 서비스',
    links: [
      { to: '/company', label: '회사 소개' },
      { to: '/pricing', label: '가격 정책' },
      { to: '/download', label: '다운로드' },
    ],
  },
  {
    label: '계정 · 커뮤니티',
    links: [
      { to: '/login', label: '로그인 / 체험하기' },
      { to: '/community', label: '커뮤니티' },
      { to: '/notices', label: '공지사항' },
    ],
  },
  {
    label: '콘텐츠',
    links: [{ to: '/insights', label: '인사이트' }],
  },
]

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer-groups">
        {FOOTER_GROUPS.map((group) => (
          <div className="site-footer-group" key={group.label}>
            <div className="site-footer-group-label">{group.label}</div>
            {group.links.map((link) => (
              <Link key={link.to} to={link.to} className="site-footer-link">
                {link.label}
              </Link>
            ))}
          </div>
        ))}
        <div className="site-footer-group">
          <div className="site-footer-group-label">문의</div>
          <a
            className="site-footer-link"
            href="https://github.com/pepper-holic/zamac_valsadae/issues"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub Issues
          </a>
        </div>
      </div>
      <p className="site-footer-notice">
        이용약관·개인정보처리방침 등 일부 페이지는 아직 초안이며 더미(예시) 데이터가 포함되어
        있습니다.
      </p>
    </footer>
  )
}
