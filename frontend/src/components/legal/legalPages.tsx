import type { LegalPageDef } from './legalPagesLegal'
import { OVERVIEW_PAGE, PRIVACY_PAGE, REFUND_PAGE, TERMS_PAGE } from './legalPagesLegal'
import {
  COMMUNITY_PAGE,
  COMPANY_PAGE,
  DOWNLOAD_PAGE,
  INSIGHTS_PAGE,
  LOGIN_PAGE,
  NOTICES_PAGE,
  PRICING_PAGE,
} from './legalPagesBiz'

export type { LegalPageDef }

export const LEGAL_PAGES: LegalPageDef[] = [
  OVERVIEW_PAGE,
  TERMS_PAGE,
  PRIVACY_PAGE,
  REFUND_PAGE,
  COMPANY_PAGE,
  PRICING_PAGE,
  DOWNLOAD_PAGE,
  LOGIN_PAGE,
  COMMUNITY_PAGE,
  NOTICES_PAGE,
  INSIGHTS_PAGE,
]

export const LEGAL_PAGE_GROUPS = Array.from(new Set(LEGAL_PAGES.map((page) => page.group)))
