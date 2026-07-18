import { GoogleLogin } from '@react-oauth/google'
import { Alert, Box } from '@mui/material'

export default function GoogleAuthButton({ onCredential, onError, text = 'continue_with' }) {
  if (!import.meta.env.VITE_GOOGLE_CLIENT_ID) {
    return <Alert severity="info">Google sign-in will appear after `VITE_GOOGLE_CLIENT_ID` is configured.</Alert>
  }
  return <Box display="flex" justifyContent="center"><GoogleLogin onSuccess={({ credential }) => onCredential(credential)} onError={onError} text={text} shape="pill" size="large" width="360" /></Box>
}
