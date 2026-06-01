import { Inbox } from 'lucide-react'

// Shared empty state — never render fake data when real data is absent.
export default function EDAEmptyState({
  message = 'No data ingested yet — upload files or connect a database to populate this view.',
  detail,
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      <div className="w-12 h-12 rounded-full bg-bg4 flex items-center justify-center mb-3">
        <Inbox size={20} className="text-t3" />
      </div>
      <div className="text-xs text-t2 max-w-md">{message}</div>
      {detail && <div className="text-[10px] text-t3 mt-1">{detail}</div>}
    </div>
  )
}
