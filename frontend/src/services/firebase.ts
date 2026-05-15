import { initializeApp, type FirebaseApp } from 'firebase/app';
import {
  EmailAuthProvider,
  createUserWithEmailAndPassword,
  GoogleAuthProvider,
  getAuth,
  onAuthStateChanged,
  reauthenticateWithCredential,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updatePassword,
  updateProfile,
  type Auth,
  type User,
} from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};
const firebaseEnabled = import.meta.env.VITE_FIREBASE_ENABLED === 'true';

let app: FirebaseApp | null = null;
let auth: Auth | null = null;
let authReady: Promise<User | null> | null = null;

export function isFirebaseAuthConfigured() {
  return Boolean(firebaseEnabled && firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId && firebaseConfig.appId);
}

function getFirebaseAuth() {
  if (!isFirebaseAuthConfigured()) return null;
  if (!app) {
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
  }
  return auth;
}

export async function waitForFirebaseUser() {
  const firebaseAuth = getFirebaseAuth();
  if (!firebaseAuth) return null;
  if (!authReady) {
    authReady = new Promise((resolve) => {
      const unsubscribe = onAuthStateChanged(firebaseAuth, (user) => {
        unsubscribe();
        resolve(user);
      });
    });
  }
  await authReady;
  return firebaseAuth.currentUser;
}

export async function getFirebaseIdToken() {
  const user = await waitForFirebaseUser();
  return user ? user.getIdToken() : null;
}

export async function signInWithFirebaseEmail(email: string, password: string) {
  const firebaseAuth = requireFirebaseAuth();
  const credential = await signInWithEmailAndPassword(firebaseAuth, email, password);
  if (!credential.user.emailVerified) {
    await signOut(firebaseAuth);
    throw new Error('Bạn cần xác minh email trước khi đăng nhập. Hãy kiểm tra hộp thư để mở liên kết xác minh.');
  }
}

export async function registerWithFirebaseEmail(email: string, password: string, displayName?: string) {
  const firebaseAuth = requireFirebaseAuth();
  const credential = await createUserWithEmailAndPassword(firebaseAuth, email, password);
  if (displayName) await updateProfile(credential.user, { displayName });
  if (!credential.user.emailVerified) {
    await sendEmailVerification(credential.user, { url: window.location.origin + '/login' });
  }
  await credential.user.getIdToken(true);
}

export async function signInWithFirebaseGoogle() {
  const firebaseAuth = requireFirebaseAuth();
  const provider = new GoogleAuthProvider();
  await signInWithPopup(firebaseAuth, provider);
}

export async function signOutFirebase() {
  const firebaseAuth = getFirebaseAuth();
  if (firebaseAuth) await signOut(firebaseAuth);
}

export async function sendFirebasePasswordReset(email: string) {
  const firebaseAuth = requireFirebaseAuth();
  await sendPasswordResetEmail(firebaseAuth, email, { url: window.location.origin + '/login' });
}

export async function changeFirebasePassword(currentPassword: string, newPassword: string) {
  const firebaseAuth = requireFirebaseAuth();
  const user = firebaseAuth.currentUser;
  if (!user?.email) throw new Error('Bạn cần đăng nhập lại trước khi đổi mật khẩu.');
  const credential = EmailAuthProvider.credential(user.email, currentPassword);
  await reauthenticateWithCredential(user, credential);
  await updatePassword(user, newPassword);
}

export async function resendFirebaseVerificationEmail() {
  const firebaseAuth = requireFirebaseAuth();
  const user = firebaseAuth.currentUser;
  if (!user) throw new Error('Bạn cần đăng nhập để gửi lại email xác minh.');
  await sendEmailVerification(user, { url: window.location.origin + '/login' });
}

function requireFirebaseAuth() {
  const firebaseAuth = getFirebaseAuth();
  if (!firebaseAuth) throw new Error('Firebase Auth chưa được cấu hình.');
  return firebaseAuth;
}
