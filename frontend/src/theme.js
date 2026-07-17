import { createTheme } from '@mui/material/styles'

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#176B52', dark: '#0D4938', light: '#D9EFE7', contrastText: '#fff' },
    secondary: { main: '#D89B28', dark: '#A76F0D' },
    background: { default: '#F4F7F5', paper: '#FFFFFF' },
    text: { primary: '#17231F', secondary: '#61706B' },
    error: { main: '#B84A4A' },
  },
  typography: {
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    h1: { fontWeight: 750, letterSpacing: '-0.04em' }, h2: { fontWeight: 750, letterSpacing: '-0.035em' },
    h3: { fontWeight: 700, letterSpacing: '-0.025em' }, h4: { fontWeight: 700, letterSpacing: '-0.02em' },
    button: { fontWeight: 650, textTransform: 'none' },
  },
  shape: { borderRadius: 14 },
  components: {
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { borderRadius: 10, paddingInline: 18 } } },
    MuiCard: { styleOverrides: { root: { border: '1px solid #E2EAE6', boxShadow: '0 8px 30px rgba(19, 62, 48, 0.06)' } } },
    MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
    MuiTextField: { defaultProps: { size: 'small' } },
  },
})

export default theme

