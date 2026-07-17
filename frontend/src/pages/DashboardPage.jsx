import { useCallback, useEffect, useState } from 'react'
import { CloudOutlined, DescriptionOutlined, FolderSharedOutlined, PersonOutlineRounded, TrendingUpRounded } from '@mui/icons-material'
import { Box, Card, CardContent, Chip, Grid, LinearProgress, Stack, Typography } from '@mui/material'
import api, { errorMessage } from '../api/client'
import { EmptyState, ErrorBlock, FileTypeChip, formatBytes, formatDate, LoadingBlock, PageIntro, UserAvatar } from '../components/Common'
import { useAuth } from '../context/AuthContext'

const statMeta = [
  ['documents', 'Accessible files', DescriptionOutlined, '#176B52', '#D9EFE7'],
  ['my_documents', 'My documents', PersonOutlineRounded, '#285BA8', '#E3ECFA'],
  ['repositories', 'Repositories', FolderSharedOutlined, '#A76F0D', '#F9EDCF'],
  ['storage_bytes', 'Storage used', CloudOutlined, '#7A4CA0', '#F0E7F7'],
]

export default function DashboardPage() {
  const { user } = useAuth(); const [data, setData] = useState(null); const [error, setError] = useState('')
  const load = useCallback(() => { setError(''); api.get('/dashboard/').then(({ data: value }) => setData(value)).catch((err) => setError(errorMessage(err))) }, [])
  useEffect(load, [load])
  if (error) return <ErrorBlock message={error} retry={load} />
  if (!data) return <LoadingBlock />
  return <><PageIntro eyebrow="Today" title={`Good day, ${user.first_name || user.username}`} subtitle="Here’s what’s happening across your document workspace." />
    <Grid container spacing={2.5} mb={3}>{statMeta.map(([key, label, Icon, color, bg]) => <Grid key={key} size={{ xs: 12, sm: 6, xl: 3 }}><Card><CardContent><Stack direction="row" justifyContent="space-between" alignItems="start"><Box><Typography color="text.secondary" variant="body2" fontWeight={600}>{label}</Typography><Typography variant="h4" mt={1}>{key === 'storage_bytes' ? formatBytes(data[key]) : data[key]}</Typography></Box><Box width={44} height={44} borderRadius={3} bgcolor={bg} color={color} display="grid" sx={{ placeItems: 'center' }}><Icon /></Box></Stack><Stack direction="row" gap={.6} alignItems="center" mt={2} color="primary.main"><TrendingUpRounded fontSize="small" /><Typography variant="caption" fontWeight={700}>Up to date</Typography></Stack></CardContent></Card></Grid>)}</Grid>
    <Grid container spacing={2.5}><Grid size={{ xs: 12, lg: 8 }}><Card><CardContent><Stack direction="row" justifyContent="space-between" mb={2.5}><Box><Typography variant="h6" fontWeight={750}>Recently updated</Typography><Typography variant="body2" color="text.secondary">Latest documents you can access</Typography></Box><Chip size="small" label={`${data.recent_documents.length} files`} /></Stack>{data.recent_documents.length ? <Stack divider={<Box borderBottom="1px solid" borderColor="divider" />}>{data.recent_documents.map((doc) => <Stack key={doc.id} direction="row" alignItems="center" gap={1.5} py={1.5}><Box width={42} height={42} flex="0 0 auto" borderRadius={2.5} bgcolor="primary.light" color="primary.dark" display="grid" sx={{ placeItems: 'center' }}><DescriptionOutlined /></Box><Box flex={1} minWidth={0}><Typography fontWeight={700} noWrap>{doc.title}</Typography><Typography variant="caption" color="text.secondary">{doc.repository_name} · {formatDate(doc.updated_at)}</Typography></Box><FileTypeChip filename={doc.latest_version?.original_filename} /></Stack>)}</Stack> : <EmptyState title="No documents yet" text="Uploaded documents will appear here." />}</CardContent></Card></Grid>
      <Grid size={{ xs: 12, lg: 4 }}><Card><CardContent><Typography variant="h6" fontWeight={750}>Recent activity</Typography><Typography variant="body2" color="text.secondary" mb={2.5}>Your latest repository events</Typography>{data.recent_activity.length ? <Stack spacing={2}>{data.recent_activity.slice(0, 6).map((event) => <Stack key={event.id} direction="row" gap={1.25}><UserAvatar user={event.actor} size={34} /><Box minWidth={0}><Typography variant="body2"><strong>{event.actor?.full_name || 'System'}</strong> {event.action.toLowerCase().replaceAll('_', ' ')}</Typography><Typography variant="caption" color="text.secondary" noWrap display="block">{event.target_name} · {formatDate(event.created_at)}</Typography></Box></Stack>)}</Stack> : <Typography color="text.secondary">No activity recorded yet.</Typography>}<Box mt={3}><Typography variant="caption" color="text.secondary">Account storage</Typography><LinearProgress variant="determinate" value={Math.min((data.storage_bytes / (5 * 1024 ** 3)) * 100, 100)} sx={{ mt: 1, height: 8, borderRadius: 8 }} /><Typography variant="caption" color="text.secondary">{formatBytes(data.storage_bytes)} of 5 GB guideline</Typography></Box></CardContent></Card></Grid>
    </Grid>
  </>
}

