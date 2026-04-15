import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { MerchantProvider } from '../src/context/MerchantContext';

export default function RootLayout() {
  return (
    <MerchantProvider>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="login" />
        <Stack.Screen name="(tabs)" />
      </Stack>
    </MerchantProvider>
  );
}
