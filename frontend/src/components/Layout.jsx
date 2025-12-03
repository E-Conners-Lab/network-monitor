import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Box,
  Flex,
  VStack,
  HStack,
  Text,
  Button,
  Icon,
  useColorModeValue,
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
  WifiOff
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

export default function Layout({ children, isConnected, onLogout }) {
  const location = useLocation();
  const [version, setVersion] = useState(null);

  // Chakra color mode values
  const sidebarBg = useColorModeValue('gray.100', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'white');
  const mutedText = useColorModeValue('gray.600', 'gray.400');

  useEffect(() => {
    system.version()
      .then(res => setVersion(res.data.version))
      .catch(() => setVersion(null));
  }, []);

  return (
    <Flex h="100vh">
      {/* Sidebar */}
      <Box
        as="aside"
        w="64"
        bg={sidebarBg}
        borderRight="1px"
        borderColor={borderColor}
        position="relative"
      >
        {/* Header */}
        <Box p={4} borderBottom="1px" borderColor={borderColor}>
          <HStack spacing={2}>
            <Icon as={Activity} boxSize={6} color="green.500" />
            <Text fontSize="xl" fontWeight="bold" color={textColor}>
              Network Monitor
            </Text>
          </HStack>
        </Box>

        {/* Navigation */}
        <Box as="nav" p={4}>
          <VStack spacing={2} align="stretch">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Button
                  key={item.path}
                  as={Link}
                  to={item.path}
                  leftIcon={<Icon as={item.icon} boxSize={5} />}
                  justifyContent="flex-start"
                  variant={isActive ? 'solid' : 'ghost'}
                  colorScheme={isActive ? 'blue' : 'gray'}
                  size="md"
                  w="full"
                  _hover={{
                    bg: isActive ? undefined : 'gray.700',
                    color: 'white',
                  }}
                >
                  {item.label}
                </Button>
              );
            })}
          </VStack>
        </Box>

        {/* Footer */}
        <Box
          position="absolute"
          bottom={0}
          left={0}
          w="full"
          p={4}
          borderTop="1px"
          borderColor={borderColor}
        >
          <HStack justify="space-between" fontSize="sm" mb={2}>
            <HStack spacing={2}>
              {isConnected ? (
                <>
                  <Icon as={Wifi} boxSize={4} color="green.500" />
                  <Text color="green.500">Connected</Text>
                </>
              ) : (
                <>
                  <Icon as={WifiOff} boxSize={4} color="red.500" />
                  <Text color="red.500">Disconnected</Text>
                </>
              )}
            </HStack>
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<Icon as={LogOut} boxSize={4} />}
              onClick={onLogout}
              color={mutedText}
              _hover={{ color: 'white' }}
            >
              Logout
            </Button>
          </HStack>
          {version && (
            <Text fontSize="xs" color="gray.500" textAlign="center">
              v{version}
            </Text>
          )}
        </Box>
      </Box>

      {/* Main content */}
      <Box as="main" flex={1} overflow="auto">
        <Box p={6}>
          {children}
        </Box>
      </Box>
    </Flex>
  );
}
