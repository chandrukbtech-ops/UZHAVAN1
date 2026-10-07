import { getApp, getApps, initializeApp } from 'firebase/app'
import * as authApi from 'firebase/auth'
import * as firestoreApi from 'firebase/firestore'
import firebaseConfig, { isFirebaseConfigured } from './firebase-config'

const app = isFirebaseConfigured
  ? getApps().length ? getApp() : initializeApp(firebaseConfig)
  : null

export const firebaseAuth = app ? authApi.getAuth(app) : null
export const firebaseDb = app ? firestoreApi.getFirestore(app) : null
export { authApi, firestoreApi }
