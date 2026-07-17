import { useCallback, useEffect, useState } from 'react'
import { HistoryOutlined, SearchRounded } from '@mui/icons-material'
import { Card, CardContent, Chip, Divider, InputAdornment, Stack, TextField, Typography } from '@mui/material'
import api, { errorMessage } from '../api/client'
import { EmptyState, ErrorBlock, formatDate, LoadingBlock, PageIntro, UserAvatar } from '../components/Common'

const colors = { CREATED: 'success', UPDATED: 'info', ARCHIVED: 'warning', RESTORED: 'success', UPLOADED_VERSION: 'secondary', DOWNLOADED: 'default', DELETED: 'error' }

export default function ActivityPage() {
  const [events, setEvents] = useState([]); const [search, setSearch] = useState(''); const [loading, setLoading] = useState(true); const [error, setError] = useState('')
  const load = useCallback(() => { setError(''); api.get(`/audit-logs/?search=${encodeURIComponent(search)}`).then(({ data }) => setEvents(data.results || data)).catch((err) => setError(errorMessage(err))).finally(() => setLoading(false)) }, [search])
  useEffect(() => { const timer = setTimeout(load, 250); return () => clearTimeout(timer) }, [load])
  return <><PageIntro eyebrow="Accountability" title="Activity log" subtitle="A traceable record of document and repository actions." /><Card><CardContent><TextField fullWidth placeholder="Search activity by file or person…" value={search} onChange={(e) => setSearch(e.target.value)} InputProps={{ startAdornment: <InputAdornment position="start"><SearchRounded /></InputAdornment> }} sx={{ mb: 2 }} />{loading ? <LoadingBlock /> : error ? <ErrorBlock message={error} retry={load} /> : events.length ? <Stack divider={<Divider />}>{events.map((event) => <Stack key={event.id} direction="row" alignItems="center" gap={1.5} py={1.75}><UserAvatar user={event.actor} size={40} /><Stack flex={1} minWidth={0}><Typography><strong>{event.actor?.full_name || 'System'}</strong> <Typography component="span" color="text.secondary">{event.action.toLowerCase().replaceAll('_', ' ')}</Typography></Typography><Typography variant="body2" fontWeight={650} noWrap>{event.target_name}</Typography><Typography variant="caption" color="text.secondary">{formatDate(event.created_at)}{event.ip_address ? ` · ${event.ip_address}` : ''}</Typography></Stack><Chip size="small" color={colors[event.action]} label={event.action.replaceAll('_', ' ')} /></Stack>)}</Stack> : <EmptyState title="No activity recorded" text="Repository actions will appear here." action={<HistoryOutlined color="primary" />} />}</CardContent></Card></>
}

