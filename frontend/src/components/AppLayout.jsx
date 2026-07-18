import { useState } from 'react'
import { AccountCircleOutlined, DashboardOutlined, FolderSharedOutlined, HistoryOutlined, LogoutRounded, MenuRounded, PeopleAltOutlined } from '@mui/icons-material'
import { AppBar, Avatar, Box, Chip, Divider, Drawer, IconButton, List, ListItemButton, ListItemIcon, ListItemText, Stack, Toolbar, Tooltip, Typography, useMediaQuery, useTheme } from '@mui/material'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { roleLabel, SchoolLogo } from './Common'
import NotificationBell from './NotificationBell'

const drawerWidth = 264
const titles = { '/': 'Overview', '/repositories': 'Repositories', '/activity': 'Activity log', '/staff': 'Staff management', '/profile': 'My profile' }

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const theme = useTheme(); const desktop = useMediaQuery(theme.breakpoints.up('md')); const location = useLocation()
  const { user, logout, isAdmin } = useAuth()
  const items = [
    { label: 'Overview', to: '/', icon: <DashboardOutlined /> },
    { label: 'Repositories', to: '/repositories', icon: <FolderSharedOutlined /> },
    { label: 'Activity log', to: '/activity', icon: <HistoryOutlined /> },
    ...(isAdmin ? [{ label: 'Staff management', to: '/staff', icon: <PeopleAltOutlined /> }] : []),
    { label: 'My profile', to: '/profile', icon: <AccountCircleOutlined /> },
  ]
  const drawer = <Box height="100%" display="flex" flexDirection="column" bgcolor="#0D4938" color="white">
    <Stack direction="row" alignItems="center" gap={1.4} px={2.5} height={72}>
      <SchoolLogo size={42} />
      <Box><Typography fontWeight={800} lineHeight={1.15}>Faculty eRepository</Typography><Typography variant="caption" sx={{ opacity: .66 }}>JSHS - Senior High School</Typography></Box>
    </Stack>
    <Divider sx={{ borderColor: 'rgba(255,255,255,.1)' }} />
    <List sx={{ px: 1.5, py: 2, flex: 1 }}>{items.map((item) => <ListItemButton key={item.to} component={NavLink} to={item.to} end={item.to === '/'} onClick={() => setMobileOpen(false)} sx={{ mb: .5, borderRadius: 2.5, color: 'rgba(255,255,255,.72)', '&.active': { bgcolor: 'rgba(255,255,255,.12)', color: '#fff' }, '&:hover': { bgcolor: 'rgba(255,255,255,.08)' } }}><ListItemIcon sx={{ minWidth: 42, color: 'inherit' }}>{item.icon}</ListItemIcon><ListItemText primary={item.label} primaryTypographyProps={{ fontSize: 14, fontWeight: 650 }} /></ListItemButton>)}</List>
    <Box p={2}><Box p={1.5} bgcolor="rgba(255,255,255,.08)" borderRadius={3}><Stack direction="row" gap={1.25} alignItems="center"><Avatar src={user?.avatar_url} sx={{ width: 38, height: 38, bgcolor: 'secondary.main' }}>{user?.first_name?.[0]}</Avatar><Box minWidth={0} flex={1}><Typography variant="body2" fontWeight={700} noWrap>{user?.full_name}</Typography><Typography variant="caption" sx={{ opacity: .65 }} noWrap>{user?.is_superuser ? 'Superadmin' : user?.position || roleLabel(user?.role)}</Typography></Box><Tooltip title="Sign out"><IconButton size="small" onClick={logout} sx={{ color: 'white' }}><LogoutRounded fontSize="small" /></IconButton></Tooltip></Stack></Box></Box>
  </Box>
  return <Box display="flex" minHeight="100vh">
    <AppBar position="fixed" color="inherit" elevation={0} sx={{ ml: { md: `${drawerWidth}px` }, width: { md: `calc(100% - ${drawerWidth}px)` }, borderBottom: '1px solid', borderColor: 'divider' }}><Toolbar sx={{ minHeight: '72px !important' }}><IconButton onClick={() => setMobileOpen(true)} sx={{ mr: 1, display: { md: 'none' } }}><MenuRounded /></IconButton><Box flex={1}><Typography variant="h6" fontWeight={750}>{titles[location.pathname] || 'eRepository'}</Typography><Typography variant="caption" color="text.secondary">Secure faculty document workspace</Typography></Box><Stack direction="row" alignItems="center" gap={1}><NotificationBell /><Chip size="small" label={user?.is_superuser ? 'SUPERADMIN' : roleLabel(user?.role)} sx={{ display: { xs: 'none', sm: 'flex' }, bgcolor: 'primary.light', color: 'primary.dark', fontWeight: 700 }} /></Stack></Toolbar></AppBar>
    <Box component="nav" width={{ md: drawerWidth }} flexShrink={{ md: 0 }}><Drawer variant={desktop ? 'permanent' : 'temporary'} open={desktop || mobileOpen} onClose={() => setMobileOpen(false)} ModalProps={{ keepMounted: true }} sx={{ '& .MuiDrawer-paper': { width: drawerWidth, border: 0 } }}>{drawer}</Drawer></Box>
    <Box component="main" flex={1} minWidth={0} pt="72px"><Box p={{ xs: 2, sm: 3, lg: 4 }} maxWidth={1500} mx="auto"><Outlet /></Box></Box>
  </Box>
}
