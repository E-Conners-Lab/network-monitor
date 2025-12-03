import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Box,
  Flex,
  HStack,
  Text,
  IconButton,
  Icon,
  Badge,
  Tooltip,
  Container,
  Spacer,
} from '@chakra-ui/react';
import {
  LayoutDashboard,
  Server,
  AlertTriangle,
  Activity,
  Wrench,
  FlaskConical,
  LogOut,
  Wifi,
  WifiOff,
  Zap
} from 'lucide-react';
import { system } from '../services/api';

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/devices', label: 'Devices', icon: Server },
  { path: '/alerts', label: 'Alerts', icon: AlertTriangle },
  { path: '/metrics', label: 'Metrics', icon: Activity },
  { path: '/remediation', label: 'Remediation', icon: Wrench },
  { path: '/tests', label: 'Tests', icon: FlaskConical },
];

// Glassmorphism card style
const glassStyle = {
  bg: 'rgba(255, 255, 255, 0.05)',
  backdropFilter: 'blur(10px)',
  border: '1px solid rgba(255, 255, 255, 0.1)',
  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
};

export default function Layout({ children, isConnected, onLogout }) {
  const location = useLocation();
  const [version, setVersion] = useState(null);

  useEffect(() => {
    system.version()
      .then(res => setVersion(res.data.version))
      .catch(() => setVersion(null));
  }, []);

  return (
    <Box minH="100vh" bg="transparent">
      {/* Top Navigation Bar - Glassmorphism Style */}
      <Box
        as="header"
        position="fixed"
        top={4}
        left={4}
        right={4}
        zIndex={100}
        {...glassStyle}
        borderRadius="2xl"
        px={6}
        py={3}
      >
        <Flex align="center">
          {/* Logo */}
          <HStack spacing={3}>
            <Box
              p={2}
              borderRadius="xl"
              bg="linear-gradient(135deg, #e94560 0%, #7b2cbf 100%)"
              boxShadow="0 4px 15px rgba(233, 69, 96, 0.4)"
            >
              <Icon as={Zap} boxSize={5} color="white" />
            </Box>
            <Box>
              <Text fontSize="lg" fontWeight="bold" color="white" letterSpacing="tight">
                NetMonitor
              </Text>
              {version && (
                <Text fontSize="xs" color="whiteAlpha.600">
                  v{version}
                </Text>
              )}
            </Box>
          </HStack>

          <Spacer />

          {/* Navigation Pills */}
          <HStack spacing={1} display={{ base: 'none', md: 'flex' }}>
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Tooltip key={item.path} label={item.label} placement="bottom">
                  <Box
                    as={Link}
                    to={item.path}
                    px={4}
                    py={2}
                    borderRadius="xl"
                    display="flex"
                    alignItems="center"
                    gap={2}
                    bg={isActive ? 'linear-gradient(135deg, #e94560 0%, #7b2cbf 100%)' : 'transparent'}
                    color={isActive ? 'white' : 'whiteAlpha.700'}
                    fontWeight={isActive ? 'semibold' : 'medium'}
                    fontSize="sm"
                    transition="all 0.3s ease"
                    _hover={{
                      bg: isActive ? undefined : 'whiteAlpha.100',
                      color: 'white',
                      transform: 'translateY(-2px)',
                    }}
                    boxShadow={isActive ? '0 4px 15px rgba(233, 69, 96, 0.4)' : 'none'}
                  >
                    <Icon as={item.icon} boxSize={4} />
                    <Text display={{ base: 'none', lg: 'block' }}>{item.label}</Text>
                  </Box>
                </Tooltip>
              );
            })}
          </HStack>

          <Spacer />

          {/* Status & Actions */}
          <HStack spacing={4}>
            {/* Connection Status */}
            <HStack
              spacing={2}
              px={3}
              py={1.5}
              borderRadius="full"
              bg={isConnected ? 'rgba(72, 187, 120, 0.2)' : 'rgba(245, 101, 101, 0.2)'}
              border="1px solid"
              borderColor={isConnected ? 'green.400' : 'red.400'}
            >
              <Icon
                as={isConnected ? Wifi : WifiOff}
                boxSize={4}
                color={isConnected ? 'green.400' : 'red.400'}
              />
              <Text
                fontSize="xs"
                fontWeight="medium"
                color={isConnected ? 'green.400' : 'red.400'}
                display={{ base: 'none', md: 'block' }}
              >
                {isConnected ? 'Live' : 'Offline'}
              </Text>
              {isConnected && (
                <Badge
                  colorScheme="green"
                  variant="solid"
                  borderRadius="full"
                  px={1.5}
                  fontSize="2xs"
                  animation="pulse 2s infinite"
                >
                  •
                </Badge>
              )}
            </HStack>

            {/* Logout Button */}
            <Tooltip label="Sign Out" placement="bottom">
              <IconButton
                icon={<Icon as={LogOut} boxSize={4} />}
                onClick={onLogout}
                variant="ghost"
                borderRadius="xl"
                color="whiteAlpha.700"
                _hover={{
                  bg: 'rgba(245, 101, 101, 0.2)',
                  color: 'red.400',
                }}
              />
            </Tooltip>
          </HStack>
        </Flex>
      </Box>

      {/* Main Content */}
      <Box
        as="main"
        pt="100px"
        pb={8}
        px={4}
        minH="100vh"
      >
        <Container maxW="container.xl">
          <Box
            {...glassStyle}
            borderRadius="2xl"
            p={6}
            minH="calc(100vh - 140px)"
          >
            {children}
          </Box>
        </Container>
      </Box>

      {/* Decorative background elements */}
      <Box
        position="fixed"
        top="20%"
        left="10%"
        w="300px"
        h="300px"
        borderRadius="full"
        bg="radial-gradient(circle, rgba(233, 69, 96, 0.15) 0%, transparent 70%)"
        filter="blur(40px)"
        pointerEvents="none"
        zIndex={-1}
      />
      <Box
        position="fixed"
        bottom="20%"
        right="10%"
        w="400px"
        h="400px"
        borderRadius="full"
        bg="radial-gradient(circle, rgba(123, 44, 191, 0.15) 0%, transparent 70%)"
        filter="blur(40px)"
        pointerEvents="none"
        zIndex={-1}
      />
    </Box>
  );
}
