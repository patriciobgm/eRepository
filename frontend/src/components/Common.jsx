import { DescriptionOutlined, InsertDriveFileOutlined } from '@mui/icons-material'
import { Alert, Avatar, Box, Button, Card, CardContent, Chip, CircularProgress, Stack, Typography } from '@mui/material'
import dayjs from 'dayjs'
import jshsLogo from '../assets/jshs-logo.PNG'

export function SchoolLogo({ size = 40 }) {
  return <Box component="img" src={jshsLogo} alt="Justino Sevilla High School logo" draggable={false} sx={{ width: size, height: size, display: 'block', objectFit: 'contain', flex: '0 0 auto' }} />
}

export function PageIntro({ eyebrow, title, subtitle, action }) {
  return <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ sm: 'center' }} gap={2} mb={3}><Box><Typography variant="overline" color="primary" fontWeight={800} letterSpacing={1.2}>{eyebrow}</Typography><Typography variant="h4" mt={-.5}>{title}</Typography><Typography color="text.secondary" mt={.5}>{subtitle}</Typography></Box>{action}</Stack>
}

export function LoadingBlock() { return <Box minHeight={280} display="grid" sx={{ placeItems: 'center' }}><CircularProgress /></Box> }
export function ErrorBlock({ message, retry }) { return <Alert severity="error" action={retry && <Button color="inherit" onClick={retry}>Retry</Button>}>{message}</Alert> }
export function EmptyState({ title, text, action }) { return <Card variant="outlined" sx={{ boxShadow: 'none' }}><CardContent sx={{ py: 7, textAlign: 'center' }}><Box mx="auto" mb={2} width={56} height={56} borderRadius={3} bgcolor="primary.light" color="primary.dark" display="grid" sx={{ placeItems: 'center' }}><DescriptionOutlined /></Box><Typography variant="h6" fontWeight={750}>{title}</Typography><Typography color="text.secondary" mt={.5} mb={2}>{text}</Typography>{action}</CardContent></Card> }
export const initials = (user) => `${user?.first_name?.[0] || ''}${user?.last_name?.[0] || ''}` || '?'
export function UserAvatar({ user, size = 36 }) { return <Avatar src={user?.avatar_url} sx={{ width: size, height: size, bgcolor: 'primary.main', fontSize: size * .36 }}>{initials(user)}</Avatar> }
export const formatBytes = (bytes = 0) => { if (!bytes) return '0 B'; const units = ['B', 'KB', 'MB', 'GB']; const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1); return `${(bytes / (1024 ** i)).toFixed(i ? 1 : 0)} ${units[i]}` }
export const formatDate = (date) => dayjs(date).format('MMM D, YYYY · h:mm A')
export const roleLabel = (role) => role === 'ASSISTANT_PRINCIPAL' ? 'Principal' : role?.replaceAll('_', ' ')
export function FileTypeChip({ filename = '' }) { const ext = filename.split('.').pop()?.toUpperCase() || 'FILE'; return <Chip icon={<InsertDriveFileOutlined />} size="small" label={ext} variant="outlined" sx={{ fontWeight: 700 }} /> }
