import { useCallback, useRef, useState } from 'react'
import api from '../../services/api'
import useStore from '../../store'

export default function UploadSurface({
  acceptAttr = '.pdf,.docx,.txt,.csv,.xlsx,.xls',
  uploadContext = {},
  showFiles = true,
  showScrape = true,
  allowFolder = false,
  helperText,
}) {
  const { addFile, setError } = useStore()
  const fileInput = useRef(null)
  const folderInput = useRef(null)
  const [scrapeUrl, setScrapeUrl] = useState('')
  const [scraping, setScraping] = useState(false)
  const [uploadWarnings, setUploadWarnings] = useState([])

  const describeError = (err, fallback) => {
    if (!err) return fallback
    if (typeof err.detail === 'string') return err.detail
    if (err.detail?.message) return err.detail.message
    if (err.message) return err.message
    return fallback
  }

  const handleFiles = useCallback(
    async (fileList) => {
      setError(null)
      for (const file of Array.from(fileList || [])) {
        try {
          const res = await api.upload(file, uploadContext)
          addFile({
            file_id: res.file_id,
            filename: file.name,
            size: file.size,
            ext: (file.name.split('.').pop() || 'txt').toUpperCase(),
            status: 'uploaded',
            pipeline_steps: {
              cleaned: false,
              chunked: false,
              entities_extracted: false,
              graph_built: false,
              indexed: false,
            },
            entities_count: 0,
            relations_count: 0,
            chunks_count: 0,
            uploaded_at: Date.now() / 1000,
            role: uploadContext.role || null,
            domain: uploadContext.domain || null,
          })
        } catch (e) {
          if (e.status === 409 && e.detail?.error === 'duplicate') {
            try {
              const forced = await api.upload(file, { ...uploadContext, force: true })
              addFile({
                file_id: forced.file_id,
                filename: file.name,
                size: file.size,
                ext: (file.name.split('.').pop() || 'txt').toUpperCase(),
                status: 'uploaded',
                pipeline_steps: {
                  cleaned: false,
                  chunked: false,
                  entities_extracted: false,
                  graph_built: false,
                  indexed: false,
                },
                entities_count: 0,
                relations_count: 0,
                chunks_count: 0,
                uploaded_at: Date.now() / 1000,
                role: uploadContext.role || null,
                domain: uploadContext.domain || null,
              })
              setUploadWarnings((w) => [
                ...w,
                {
                  filename: file.name,
                  message: 'Duplicate detected and force re-uploaded successfully.',
                  original_file_id: e.detail.original_file_id,
                  original_filename: e.detail.original_filename,
                },
              ])
            } catch (forceErr) {
              setUploadWarnings((w) => [
                ...w,
                {
                  filename: file.name,
                  message: `Force re-upload failed: ${forceErr.message || 'unknown error'}`,
                  original_file_id: e.detail.original_file_id,
                  original_filename: e.detail.original_filename,
                },
              ])
            }
          } else {
            const message = describeError(e, 'Upload failed')
            setError(`Upload failed for ${file.name}: ${message}`)
            setUploadWarnings((w) => [
              ...w,
              {
                filename: file.name,
                message,
                original_file_id: null,
                original_filename: null,
              },
            ])
          }
        }
      }
    },
    [addFile, setError, uploadContext],
  )

  const handleDrop = (e) => {
    e.preventDefault()
    handleFiles(e.dataTransfer.files)
  }

  const handleScrape = async () => {
    if (!scrapeUrl.trim()) return
    setError(null)
    setScraping(true)
    try {
      const res = await api.scrape(scrapeUrl.trim(), uploadContext)
      addFile({
        file_id: res.file_id,
        filename: `${scrapeUrl.slice(0, 40)}_scraped.txt`,
        size: res.chars,
        ext: 'TXT',
        status: 'uploaded',
        pipeline_steps: {
          cleaned: false,
          chunked: false,
          entities_extracted: false,
          graph_built: false,
          indexed: false,
        },
        entities_count: 0,
        relations_count: 0,
        chunks_count: 0,
        uploaded_at: Date.now() / 1000,
        role: uploadContext.role || null,
        domain: uploadContext.domain || null,
      })
      setScrapeUrl('')
    } catch (e) {
      if (e.status === 409 && e.detail?.error === 'duplicate') {
        try {
          const forced = await api.scrape(scrapeUrl.trim(), { ...uploadContext, force: true })
          addFile({
            file_id: forced.file_id,
            filename: `${scrapeUrl.slice(0, 40)}_scraped.txt`,
            size: forced.chars,
            ext: 'TXT',
            status: 'uploaded',
            pipeline_steps: {
              cleaned: false,
              chunked: false,
              entities_extracted: false,
              graph_built: false,
              indexed: false,
            },
            entities_count: 0,
            relations_count: 0,
            chunks_count: 0,
            uploaded_at: Date.now() / 1000,
            role: uploadContext.role || null,
            domain: uploadContext.domain || null,
          })
          setUploadWarnings((w) => [
            ...w,
            {
              filename: 'URL scrape',
              message: 'Duplicate URL content detected and force re-ingested successfully.',
              original_file_id: e.detail.original_file_id,
              original_filename: e.detail.original_filename,
            },
          ])
          setScrapeUrl('')
        } catch (forceErr) {
          const message = describeError(forceErr, 'unknown error')
          setError(`Force scrape failed: ${message}`)
          setUploadWarnings((w) => [
            ...w,
            {
              filename: 'URL scrape',
              message: `Force scrape failed: ${message}`,
              original_file_id: e.detail?.original_file_id || null,
              original_filename: e.detail?.original_filename || null,
            },
          ])
        }
      } else {
        const message = describeError(e, 'Scrape failed')
        setError(`Scrape failed: ${message}`)
        setUploadWarnings((w) => [
          ...w,
          {
            filename: 'URL scrape',
            message,
            original_file_id: null,
            original_filename: null,
          },
        ])
      }
    } finally {
      setScraping(false)
    }
  }

  return (
    <div className="space-y-3">
      {uploadWarnings.length > 0 && (
        <div className="space-y-1.5">
          {uploadWarnings.map((w, i) => (
            <div
              key={i}
              className="flex items-start gap-2.5 px-3.5 py-2.5 rounded-sm text-[11px]"
              style={{ background: 'rgba(217,119,6,.08)', border: '1px solid rgba(217,119,6,.30)', color: '#d97706' }}
            >
              <span className="flex-shrink-0 mt-0.5">⚠</span>
              <div>
                <span className="font-semibold">{w.filename}</span> — {w.message}
                <span className="ml-1.5 text-[10px] opacity-70">
                  (original ID: {w.original_file_id?.slice(0, 8)}…)
                </span>
              </div>
              <button
                className="ml-auto flex-shrink-0 opacity-60 hover:opacity-100"
                onClick={() => setUploadWarnings((prev) => prev.filter((_, j) => j !== i))}
              >✕</button>
            </div>
          ))}
        </div>
      )}

      {showFiles && (
      <div
        className="border border-dashed border-dborder2 rounded-card p-7 text-center cursor-pointer bg-card transition-all hover:border-accent hover:bg-accent/5"
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => fileInput.current?.click()}
      >
        <input
          ref={fileInput}
          type="file"
          multiple
          accept={acceptAttr}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        {allowFolder && (
          <input
            ref={folderInput}
            type="file"
            webkitdirectory=""
            directory=""
            multiple
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
        )}
        <div className="w-10 h-10 bg-bg4 border border-dborder rounded-sm flex items-center justify-center mx-auto mb-2.5">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path
              d="M9 2.5v10M6 5.5l3-3 3 3M3 13h12v2H3z"
              stroke="#4f46e5"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <div className="text-[12px] text-t2">
          Drop files or <span className="text-accent font-medium">click to browse</span>
          {allowFolder && (
            <>
              {' · '}
              <span
                className="text-accent font-medium"
                onClick={(e) => {
                  e.stopPropagation()
                  folderInput.current?.click()
                }}
              >
                pick folder
              </span>
            </>
          )}
        </div>
        <div className="text-[10px] text-t3 mt-1">
          {helperText || `Supports ${acceptAttr.replaceAll(',', ' · ').replaceAll('.', '').toUpperCase()}`}
        </div>
      </div>
      )}

      {showScrape && (
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Or paste a URL: https://example.com/page"
            value={scrapeUrl}
            onChange={(e) => setScrapeUrl(e.target.value)}
            className="flex-1 bg-bg3 border border-dborder2 rounded-sm px-4 py-2 text-[12px] text-t1 outline-none focus:border-accent"
            onKeyDown={(e) => e.key === 'Enter' && handleScrape()}
          />
          <button className="btn btn-p btn-sm" onClick={handleScrape} disabled={scraping}>
            {scraping ? 'Scraping…' : 'Scrape & ingest'}
          </button>
        </div>
      )}
    </div>
  )
}
