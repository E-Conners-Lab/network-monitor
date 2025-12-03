import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ChakraProvider, extendTheme } from '@chakra-ui/react'
import App from './App'

// Modern gradient theme - completely different from TailwindCSS version
const theme = extendTheme({
  config: {
    initialColorMode: 'dark',
    useSystemColorMode: false,
  },
  styles: {
    global: {
      body: {
        bg: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        color: 'white',
        minHeight: '100vh',
      },
    },
  },
  colors: {
    brand: {
      50: '#e0f7fa',
      100: '#b2ebf2',
      200: '#80deea',
      300: '#4dd0e1',
      400: '#26c6da',
      500: '#00bcd4',
      600: '#00acc1',
      700: '#0097a7',
      800: '#00838f',
      900: '#006064',
    },
    accent: {
      pink: '#e94560',
      purple: '#7b2cbf',
      teal: '#00d9ff',
      orange: '#ff6b35',
    },
  },
  components: {
    Button: {
      baseStyle: {
        fontWeight: 'semibold',
        borderRadius: 'xl',
      },
      variants: {
        solid: {
          bg: 'linear-gradient(135deg, #e94560 0%, #7b2cbf 100%)',
          color: 'white',
          _hover: {
            bg: 'linear-gradient(135deg, #ff6b7a 0%, #9b4edf 100%)',
            transform: 'translateY(-2px)',
            boxShadow: '0 10px 20px rgba(233, 69, 96, 0.3)',
          },
          transition: 'all 0.3s ease',
        },
        ghost: {
          _hover: {
            bg: 'whiteAlpha.100',
          },
        },
      },
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ChakraProvider theme={theme}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ChakraProvider>
  </React.StrictMode>,
)
