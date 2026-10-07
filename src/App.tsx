import { useEffect, useRef, useState } from 'react'
import type { User } from 'firebase/auth'
import {
  AlertCircle,
  ArrowLeftRight,
  Bell,
  CalendarDays,
  Camera,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  CloudRain,
  CloudSun,
  Droplets,
  House,
  ImagePlus,
  Leaf,
  LoaderCircle,
  MapPin,
  MapPinned,
  Mic,
  MessageCircle,
  ScanLine,
  Send,
  ShieldCheck,
  Sprout,
  ThermometerSun,
  Tractor,
  Upload,
  Volume2,
  Wind,
  X,
} from 'lucide-react'
import { isFirebaseConfigured } from './firebase-config'
import './App.css'

type Language = 'en' | 'ta'
type FacingMode = 'environment' | 'user'
type Tab = 'home' | 'scan' | 'assistant' | 'weather' | 'farm' | 'reminders'

type FarmerProfile = {
  farmName: string
  district: string
  area: string
  soil: string
  water: string
}

type FarmReminder = {
  id: string
  crop: string
  task: string
  due: string
  note: string
  done: boolean
  notified: boolean
}

type WeatherSnapshot = {
  temperature: number
  humidity: number
  rain: number
  wind: number
  code: number
  days: Array<{ date: string; min: number; max: number; rain: number; code: number }>
}

type SpeechRecognitionLike = {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onerror: ((event: Event) => void) | null
  onend: (() => void) | null
  start: () => void
}

type Prediction = {
  status: 'identified' | 'not_sure'
  crop: string | null
  condition: string | null
  disease: string | null
  confidence: number
}

const crops = [
  { id: 'rice', en: 'Rice', ta: 'நெல்' },
  { id: 'wheat', en: 'Wheat', ta: 'கோதுமை' },
  { id: 'corn', en: 'Corn', ta: 'மக்காச்சோளம்' },
  { id: 'sugarcane', en: 'Sugarcane', ta: 'கரும்பு' },
  { id: 'cotton', en: 'Cotton', ta: 'பருத்தி' },
  { id: 'soybean', en: 'Soybean', ta: 'சோயாபீன்' },
  { id: 'mustard', en: 'Mustard', ta: 'கடுகு' },
  { id: 'tomato', en: 'Tomato', ta: 'தக்காளி' },
  { id: 'brinjal', en: 'Brinjal', ta: 'கத்தரிக்காய்' },
]

const cropGuides = [
  { id: 'rice', soils: ['clay', 'alluvial'], water: 'high', reason: 'Performs best where reliable irrigation or seasonal water is available.' },
  { id: 'wheat', soils: ['loam', 'alluvial'], water: 'medium', reason: 'A practical option for well-drained loam with a cool growing window.' },
  { id: 'corn', soils: ['loam', 'red'], water: 'medium', reason: 'Adaptable on well-drained soils when moisture is available at flowering.' },
  { id: 'sugarcane', soils: ['loam', 'alluvial'], water: 'high', reason: 'Needs a long growing period, dependable water, and a nearby market.' },
  { id: 'cotton', soils: ['black', 'red'], water: 'low', reason: 'Often suited to black soils; avoid waterlogging and check local variety advice.' },
  { id: 'soybean', soils: ['black', 'loam'], water: 'medium', reason: 'Can fit well-drained black soil where rainfall is dependable.' },
  { id: 'mustard', soils: ['loam', 'alluvial'], water: 'low', reason: 'A lower-water option for a suitable cool, dry season.' },
  { id: 'tomato', soils: ['sandy', 'loam', 'red'], water: 'medium', reason: 'Needs steady moisture and good drainage; drip irrigation is useful.' },
  { id: 'brinjal', soils: ['loam', 'red', 'alluvial'], water: 'medium', reason: 'Can suit warm conditions with fertile, well-drained soil.' },
]

const irrigationMethods: Record<string, string> = {
  rice: 'Shallow field irrigation; consider alternate wetting and drying where locally advised.',
  wheat: 'Border or furrow irrigation; apply at locally recommended critical growth stages.',
  corn: 'Drip or furrow irrigation; protect moisture around flowering and grain fill.',
  sugarcane: 'Drip irrigation is efficient; furrow irrigation is another option with good drainage.',
  cotton: 'Drip or furrow irrigation; avoid standing water around roots.',
  soybean: 'Rainfall-led or sprinkler irrigation; avoid waterlogging.',
  mustard: 'Need-based light irrigation; avoid excess water and waterlogging.',
  tomato: 'Drip irrigation is preferred for steady root-zone moisture and dry foliage.',
  brinjal: 'Drip or furrow irrigation; keep moisture even and provide drainage.',
}

const cropCareGuides: Record<string, string> = {
  rice: 'Irrigate by field water level and crop stage. Split nitrogen top-dressing is commonly timed around active tillering and panicle initiation; confirm with a soil test and local schedule.',
  wheat: 'Check soil moisture before irrigation. Nitrogen is usually split between sowing and early growth stages; use the local crop calendar and soil-test rate.',
  corn: 'Check moisture near the root zone, especially before flowering. Split fertilizer by growth stage; do not apply just before heavy rain.',
  sugarcane: 'Use soil moisture and the crop stage to plan irrigation. Split fertilizer through active growth according to local recommendations.',
  soybean: 'Avoid excess irrigation and waterlogging. Base any nutrient correction on soil testing; do not assume nitrogen is needed without local advice.',
  mustard: 'Use light, need-based irrigation and avoid waterlogging. Follow soil-test recommendations for fertilizer and crop stage.',
  tomato: 'Keep root-zone moisture steady, preferably with drip. Apply nutrients in stages based on soil testing and the crop’s growth phase.',
  brinjal: 'Maintain even soil moisture and good drainage. Use soil-test-based split feeding during vegetative and fruiting growth.',
  corn_general: 'Check root-zone moisture before watering. Time fertilizer by crop stage and soil-test guidance.',
}

const tabItems: Array<{ id: Tab; label: string; icon: typeof House }> = [
  { id: 'home', label: 'Home', icon: House },
  { id: 'scan', label: 'Scan', icon: ScanLine },
  { id: 'assistant', label: 'Advisor', icon: MessageCircle },
  { id: 'weather', label: 'Weather', icon: CloudSun },
  { id: 'farm', label: 'Farm', icon: Tractor },
  { id: 'reminders', label: 'Tasks', icon: Bell },
]

function localDateTime(offsetHours = 24) {
  const date = new Date(Date.now() + offsetHours * 60 * 60 * 1000)
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset())
  return date.toISOString().slice(0, 16)
}

function weatherDescription(code: number) {
  if (code === 0) return 'Clear sky'
  if (code <= 3) return 'Partly cloudy'
  if (code <= 48) return 'Foggy'
  if (code <= 67) return 'Rain showers'
  if (code <= 77) return 'Snow or hail'
  if (code <= 82) return 'Rain showers'
  if (code <= 86) return 'Snow showers'
  return 'Thunderstorm'
}

const copy = {
  en: {
    kicker: 'CROP IDENTIFICATION',
    title: 'What’s growing?',
    subtitle: 'Upload a clear leaf photo to identify the crop.',
    modelReady: 'Model ready',
    modelMissing: 'Model not trained yet',
    serviceOffline: 'Service offline',
    photoTitle: 'Add a leaf photo',
    photoHint: 'Use a clear, single leaf in natural light for the best match.',
    upload: 'Upload photo',
    camera: 'Open camera',
    capture: 'Take photo',
    switchCamera: 'Switch camera',
    useAnother: 'Choose another photo',
    analyze: 'Identify crop',
    analyzing: 'Checking leaf…',
    resultTitle: 'IDENTIFICATION',
    waitingTitle: 'Your result will appear here',
    waitingHint: 'Add a photo to get started.',
    sure: 'Best match',
    diseaseDetected: 'Leaf condition',
    healthyLeaf: 'Healthy leaf',
    notSure: 'We couldn’t identify this leaf',
    notSureHint: 'Try a sharper photo with one leaf in focus.',
    confidence: 'Model confidence',
    supported: 'SUPPORTED CROPS',
    modelNote: 'Crop model is not ready. Train it with labeled leaf photos.',
    apiOfflineNote: 'Crop service is offline. Start the API and refresh.',
    cameraDenied: 'Camera unavailable. Allow access or upload a photo.',
    uploadError: 'Choose a JPG, PNG, or WebP image under 12 MB.',
    apiError: 'Could not reach the crop service. Check that the API is running.',
    retake: 'Retake',
    privacy: 'Photos are analyzed but never saved.',
    assistantTitle: 'Farm advisor',
    assistantSubtitle: 'Ask about crops, pests, soil, or irrigation.',
    assistantPlaceholder: 'Ask a question about your field…',
    send: 'Send',
    diseaseLoading: 'Preparing precautions…',
    diseaseResultTitle: 'Possible causes and precautions',
    diseaseDisclaimer: 'This is not a confirmed diagnosis. Check with your local agriculture office before treatment.',
    listening: 'Listening…',
    voiceNote: 'Voice support is ready',
    voiceUnavailable: 'Voice input is not supported in this browser.',
    assistantReady: 'Hello. Ask me about crop health, soil, pests, or irrigation.',
  },
  ta: {
    kicker: 'பயிர் அடையாளம்',
    title: 'என்ன பயிர் இது?',
    subtitle: 'பயிரை அடையாளம் காண தெளிவான இலைப் படத்தைப் பதிவேற்றுங்கள்.',
    modelReady: 'மாதிரி தயார்',
    modelMissing: 'மாதிரி இன்னும் பயிற்சி பெறவில்லை',
    serviceOffline: 'சேவை இயங்கவில்லை',
    photoTitle: 'இலைப் படத்தைச் சேர்க்கவும்',
    photoHint: 'சிறந்த முடிவுக்கு இயற்கை வெளிச்சத்தில் தெளிவான ஒற்றை இலையைப் படம் எடுக்கவும்.',
    upload: 'படத்தைப் பதிவேற்று',
    camera: 'கேமராவைத் திற',
    capture: 'படம் எடு',
    switchCamera: 'கேமராவை மாற்று',
    useAnother: 'வேறு படத்தைத் தேர்ந்தெடு',
    analyze: 'பயிரைக் கண்டறி',
    analyzing: 'இலையைப் பார்க்கிறோம்…',
    resultTitle: 'அடையாளம்',
    waitingTitle: 'முடிவு இங்கே தெரியும்',
    waitingHint: 'தொடங்க ஒரு படத்தைச் சேர்க்கவும்.',
    sure: 'சிறந்த பொருத்தம்',
    diseaseDetected: 'இலை நிலை',
    healthyLeaf: 'ஆரோக்கியமான இலை',
    notSure: 'இந்த இலையை அடையாளம் காண முடியவில்லை',
    notSureHint: 'ஒரு இலையை மட்டும் தெளிவாகப் படம் எடுத்து முயற்சிக்கவும்.',
    confidence: 'மாதிரியின் நம்பிக்கை',
    supported: 'ஆதரிக்கப்படும் பயிர்கள்',
    modelNote: 'பயிர் மாதிரி தயாராக இல்லை. பெயரிடப்பட்ட இலைப் படங்களைக் கொண்டு பயிற்சி அளிக்கவும்.',
    apiOfflineNote: 'பயிர் சேவை இயங்கவில்லை. API-ஐத் தொடங்கி மீண்டும் ஏற்றவும்.',
    cameraDenied: 'கேமரா கிடைக்கவில்லை. அனுமதி வழங்கவும் அல்லது படத்தைப் பதிவேற்றவும்.',
    uploadError: '12 MB-க்கு குறைவான JPG, PNG அல்லது WebP படத்தைத் தேர்ந்தெடுக்கவும்.',
    apiError: 'பயிர் சேவையை அணுக முடியவில்லை. API இயங்குகிறதா எனச் சரிபார்க்கவும்.',
    retake: 'மீண்டும் எடு',
    privacy: 'படங்கள் ஆய்வு செய்யப்படும்; சேமிக்கப்படாது.',
    assistantTitle: 'விவசாய ஆலோசகர்',
    assistantSubtitle: 'பயிர், பூச்சி, மண் அல்லது பாசனம் பற்றி கேளுங்கள்.',
    assistantPlaceholder: 'வயல் தொடர்பான கேள்வியைக் கேளுங்கள்…',
    send: 'அனுப்பு',
    diseaseLoading: 'முன்னெச்சரிக்கைகளைத் தயாரிக்கிறது…',
    diseaseResultTitle: 'சாத்தியமான காரணங்களும் முன்னெச்சரிக்கைகளும்',
    diseaseDisclaimer: 'இது உறுதியான நோய் கண்டறிதல் அல்ல. சிகிச்சைக்கு முன் உள்ளூர் வேளாண் அலுவலரை அணுகவும்.',
    listening: 'கேக்கிறேன்…',
    voiceNote: 'குரல் ஆதரவு தயாராக உள்ளது',
    voiceUnavailable: 'இந்த உலாவியில் குரல் உள்ளீடு கிடைக்கவில்லை.',
    assistantReady: 'வணக்கம். பயிர், மண், பூச்சி அல்லது பாசனம் பற்றி கேளுங்கள்.',
  },
} satisfies Record<Language, Record<string, string>>

function App() {
  const [language, setLanguage] = useState<Language>('en')
  const [activeTab, setActiveTab] = useState<Tab>('home')
  const [isBooting, setIsBooting] = useState(true)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [photo, setPhoto] = useState<File | null>(null)
  const [cameraOpen, setCameraOpen] = useState(false)
  const [facingMode, setFacingMode] = useState<FacingMode>('environment')
  const [cameraError, setCameraError] = useState(false)
  const [modelReady, setModelReady] = useState(false)
  const [supportedCrops, setSupportedCrops] = useState<string[]>(crops.map((crop) => crop.id))
  const [apiOnline, setApiOnline] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [prediction, setPrediction] = useState<Prediction | null>(null)
  const [chatInput, setChatInput] = useState('')
  const [scanDiseaseAnswer, setScanDiseaseAnswer] = useState('')
  const [scanDiseaseLoading, setScanDiseaseLoading] = useState(false)
  const [scanDiseaseError, setScanDiseaseError] = useState('')
  const t = copy[language]
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string }>>([
    { role: 'assistant', text: t.assistantReady },
  ])
  const [chatLoading, setChatLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [assistantMode, setAssistantMode] = useState<'local_model' | 'local_notes'>('local_notes')
  const [weather, setWeather] = useState<WeatherSnapshot | null>(null)
  const [weatherLoading, setWeatherLoading] = useState(false)
  const [weatherError, setWeatherError] = useState('')
  const [locationName, setLocationName] = useState('Location needed')
  const [farmProfile, setFarmProfile] = useState<FarmerProfile>(() => {
    try {
      const saved = localStorage.getItem('uzhavan-farm-profile')
      return saved ? { farmName: '', district: '', area: '', soil: 'loam', water: 'reliable', ...JSON.parse(saved) } : { farmName: '', district: '', area: '', soil: 'loam', water: 'reliable' }
    } catch {
      return { farmName: '', district: '', area: '', soil: 'loam', water: 'reliable' }
    }
  })
  const [user, setUser] = useState<User | null>(null)
  const [authReady, setAuthReady] = useState(!isFirebaseConfigured)
  const [showAuth, setShowAuth] = useState(false)
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>('signin')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [authLoading, setAuthLoading] = useState(false)
  const [storageReady, setStorageReady] = useState(!isFirebaseConfigured)
  const [storageError, setStorageError] = useState('')
  const [recommendations, setRecommendations] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('uzhavan-farm-recommendations') ?? '[]') as string[]
    } catch {
      return []
    }
  })
  const [reminders, setReminders] = useState<FarmReminder[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('uzhavan-farm-reminders') ?? '[]') as FarmReminder[]
    } catch {
      return []
    }
  })
  const [reminderCrop, setReminderCrop] = useState('rice')
  const [reminderTask, setReminderTask] = useState('Water / irrigation')
  const [reminderDue, setReminderDue] = useState(localDateTime())
  const [reminderNote, setReminderNote] = useState('')
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const chatEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let active = true
    fetch('/api/health')
      .then((response) => response.json())
      .then((health: { model_ready?: boolean; supported_crops?: string[]; assistant_mode?: string }) => {
        if (active) {
          setApiOnline(true)
          setModelReady(health.model_ready === true)
          setAssistantMode(health.assistant_mode === 'local_model' ? 'local_model' : 'local_notes')
          if (health.model_ready && Array.isArray(health.supported_crops)) {
            setSupportedCrops(health.supported_crops)
          }
        }
      })
      .catch(() => {
        if (active) {
          setApiOnline(false)
          setModelReady(false)
        }
      })
      .finally(() => {
        window.setTimeout(() => {
          if (active) setIsBooting(false)
        }, 550)
      })

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!isFirebaseConfigured) return
    let active = true
    let generation = 0
    let stopReminderListener: (() => void) | undefined
    let stopAuthListener: (() => void) | undefined

    void import('./firebase').then(({ firebaseAuth, firebaseDb, authApi, firestoreApi }) => {
      if (!active) return
      if (!firebaseAuth || !firebaseDb) {
        setStorageError('Firebase is configured incompletely. Check the project settings.')
        setStorageReady(true)
        setAuthReady(true)
        return
      }

      stopAuthListener = authApi.onAuthStateChanged(firebaseAuth, async (nextUser) => {
        const currentGeneration = ++generation
        stopReminderListener?.()
        setStorageReady(false)
        setStorageError('')
        setUser(nextUser)

        if (!nextUser) {
          try {
            const storedProfile = localStorage.getItem('uzhavan-farm-profile')
            const storedReminders = localStorage.getItem('uzhavan-farm-reminders')
            const storedRecommendations = localStorage.getItem('uzhavan-farm-recommendations')
            setFarmProfile(storedProfile
              ? { farmName: '', district: '', area: '', soil: 'loam', water: 'reliable', ...JSON.parse(storedProfile) as Partial<FarmerProfile> }
              : { farmName: '', district: '', area: '', soil: 'loam', water: 'reliable' })
            setReminders(storedReminders ? JSON.parse(storedReminders) as FarmReminder[] : [])
            setRecommendations(storedRecommendations ? JSON.parse(storedRecommendations) as string[] : [])
            setStorageReady(true)
          } catch {
            setStorageError('Could not load farm data saved on this device.')
          } finally {
            setAuthReady(true)
          }
          return
        }

        try {
          const profileSnapshot = await firestoreApi.getDoc(firestoreApi.doc(firebaseDb, 'users', nextUser.uid, 'private', 'farm'))
          if (currentGeneration !== generation) return
          if (profileSnapshot.exists()) {
            const profileData = profileSnapshot.data()
            const { recommendations: savedRecommendations, ...savedProfile } = profileData
            setFarmProfile((current) => ({ ...current, ...savedProfile as Partial<FarmerProfile> }))
            setRecommendations(Array.isArray(savedRecommendations) ? savedRecommendations as string[] : [])
          } else {
            setFarmProfile({ farmName: '', district: '', area: '', soil: 'loam', water: 'reliable' })
            setRecommendations([])
          }
          stopReminderListener = firestoreApi.onSnapshot(
            firestoreApi.collection(firebaseDb, 'users', nextUser.uid, 'reminders'),
            (snapshot) => {
              setReminders(snapshot.docs.map((reminder) => ({ id: reminder.id, ...reminder.data() }) as FarmReminder))
              setStorageReady(true)
            },
            () => {
              setStorageError('Could not sync your tasks. Check your Firebase Firestore rules.')
              setStorageReady(true)
            },
          )
        } catch {
          if (currentGeneration === generation) {
            setStorageError('Could not load your farm data from Firebase.')
            setStorageReady(true)
          }
        } finally {
          setAuthReady(true)
        }
      })
    }).catch(() => {
      if (active) {
        setStorageError('Could not load Firebase. Check your connection and app configuration.')
        setStorageReady(true)
        setAuthReady(true)
      }
    })

    return () => {
      active = false
      generation += 1
      stopReminderListener?.()
      stopAuthListener?.()
    }
  }, [])

  useEffect(() => {
    if (!authReady || !storageReady) return
    if (!user) {
      localStorage.setItem('uzhavan-farm-profile', JSON.stringify(farmProfile))
      localStorage.setItem('uzhavan-farm-recommendations', JSON.stringify(recommendations))
      return
    }
    const saveTimer = window.setTimeout(() => {
      void import('./firebase').then(({ firebaseDb, firestoreApi }) => {
        if (!firebaseDb) throw new Error('Firebase Firestore is unavailable.')
        return firestoreApi.setDoc(firestoreApi.doc(firebaseDb, 'users', user.uid, 'private', 'farm'), { ...farmProfile, recommendations })
      }).then(() => setStorageError(''))
        .catch(() => setStorageError('Could not save your farm details. Check your Firestore rules.'))
    }, 700)
    return () => window.clearTimeout(saveTimer)
  }, [authReady, farmProfile, recommendations, storageReady, user])

  useEffect(() => {
    if (!authReady || !storageReady || user) return
    localStorage.setItem('uzhavan-farm-reminders', JSON.stringify(reminders))
  }, [authReady, reminders, storageReady, user])

  useEffect(() => {
    const interval = window.setInterval(() => {
      const due = reminders.filter((reminder) => !reminder.done && !reminder.notified && new Date(reminder.due).getTime() <= Date.now())
      if (!due.length) return
      if ('Notification' in window && Notification.permission === 'granted') {
        due.forEach((reminder) => new Notification(`${reminder.task}: ${reminder.crop}`, { body: reminder.note || 'Your farm reminder is due.' }))
      }
      const dueIds = new Set(due.map((reminder) => reminder.id))
      setReminders((current) => current.map((reminder) => dueIds.has(reminder.id) ? { ...reminder, notified: true } : reminder))
      if (user) {
        void import('./firebase').then(({ firebaseDb, firestoreApi }) => {
          if (!firebaseDb) throw new Error('Firebase Firestore is unavailable.')
          return Promise.all(due.map((reminder) => firestoreApi.setDoc(
            firestoreApi.doc(firebaseDb, 'users', user.uid, 'reminders', reminder.id),
            { ...reminder, notified: true },
          )))
        }).catch(() => setStorageError('Could not sync reminder status to Firebase.'))
      }
    }, 30000)
    return () => window.clearInterval(interval)
  }, [reminders, user])

  useEffect(() => {
    if (!previewUrl) return
    return () => URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  useEffect(() => {
    if (!cameraOpen) return
    let stream: MediaStream | null = null
    let active = true

    navigator.mediaDevices
      .getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: facingMode },
          width: { ideal: 1600 },
          height: { ideal: 1200 },
        },
      })
      .then((mediaStream) => {
        if (!active) {
          mediaStream.getTracks().forEach((track) => track.stop())
          return
        }
        stream = mediaStream
        if (videoRef.current) videoRef.current.srcObject = mediaStream
        setCameraError(false)
      })
      .catch(() => {
        if (active) setCameraError(true)
      })

    return () => {
      active = false
      stream?.getTracks().forEach((track) => track.stop())
    }
  }, [cameraOpen, facingMode])

  async function submitAuthentication(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!isFirebaseConfigured) {
      setAuthError('Firebase is not configured. Add the project settings to .env.local and restart the app.')
      return
    }

    setAuthLoading(true)
    setAuthError('')
    try {
      const { firebaseAuth, authApi } = await import('./firebase')
      if (!firebaseAuth) throw new Error('Firebase Authentication is unavailable.')
      if (authMode === 'signup') {
        await authApi.createUserWithEmailAndPassword(firebaseAuth, authEmail.trim(), authPassword)
      } else {
        await authApi.signInWithEmailAndPassword(firebaseAuth, authEmail.trim(), authPassword)
      }
      setShowAuth(false)
      setAuthPassword('')
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : 'Could not sign in. Please try again.')
    } finally {
      setAuthLoading(false)
    }
  }

  async function signInWithGoogle() {
    if (!isFirebaseConfigured) {
      setAuthError('Firebase is not configured. Add the project settings to .env.local and restart the app.')
      return
    }
    setAuthLoading(true)
    setAuthError('')
    try {
      const { firebaseAuth, authApi } = await import('./firebase')
      if (!firebaseAuth) throw new Error('Firebase Authentication is unavailable.')
      await authApi.signInWithPopup(firebaseAuth, new authApi.GoogleAuthProvider())
      setShowAuth(false)
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : 'Could not sign in with Google.')
    } finally {
      setAuthLoading(false)
    }
  }

  async function signOutUser() {
    try {
      const { firebaseAuth, authApi } = await import('./firebase')
      if (!firebaseAuth) throw new Error('Firebase Authentication is unavailable.')
      await authApi.signOut(firebaseAuth)
    } catch {
      setStorageError('Could not sign out. Please try again.')
    }
  }

  function acceptPhoto(file: File | undefined) {
    if (!file) return
    if (!file.type.startsWith('image/') || file.size > 12 * 1024 * 1024) {
      setError(t.uploadError)
      return
    }
    setError(null)
    setPrediction(null)
    setPhoto(file)
    setPreviewUrl(URL.createObjectURL(file))
  }

  function openCamera() {
    setCameraError(false)
    setError(null)
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError(true)
      setError(t.cameraDenied)
      return
    }
    setCameraOpen(true)
  }

  function capturePhoto() {
    const video = videoRef.current
    if (!video?.videoWidth || !video.videoHeight) return
    const canvas = document.createElement('canvas')
    const scale = Math.min(1, 1600 / video.videoWidth)
    canvas.width = Math.round(video.videoWidth * scale)
    canvas.height = Math.round(video.videoHeight * scale)
    const context = canvas.getContext('2d')
    if (!context) return
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob((blob) => {
      if (!blob) return
      acceptPhoto(new File([blob], 'uzhavan-leaf.jpg', { type: 'image/jpeg' }))
      setCameraOpen(false)
    }, 'image/jpeg', 0.88)
  }

  function clearPhoto() {
    setPhoto(null)
    setPreviewUrl(null)
    setPrediction(null)
    setError(null)
  }

  function speakAnswer(text: string) {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    const utterance = new SpeechSynthesisUtterance(text)
    const targetLanguage = /[\u0b80-\u0bff]/.test(text) ? 'ta-IN' : language === 'ta' ? 'ta-IN' : 'en'
    utterance.lang = targetLanguage
    utterance.rate = 0.92
    utterance.pitch = 1
    utterance.volume = 0.82
    const languageVoices = window.speechSynthesis.getVoices()
      .filter((voice) => voice.lang.toLowerCase().startsWith(targetLanguage.slice(0, 2)))
    const naturalVoice = languageVoices.find((voice) =>
      /natural|premium|enhanced|neural|samantha|ava|karen|moira|tessa/i.test(voice.name),
    )
    const exactLanguageVoice = languageVoices.find((voice) =>
      voice.lang.toLowerCase() === targetLanguage.toLowerCase(),
    )
    utterance.voice = naturalVoice ?? exactLanguageVoice ?? languageVoices[0] ?? null
    utterance.onstart = () => setIsSpeaking(true)
    utterance.onend = () => setIsSpeaking(false)
    utterance.onerror = () => setIsSpeaking(false)
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utterance)
  }

  async function askAssistant(input = chatInput) {
    const question = input.trim()
    if (!question || chatLoading) return

    setChatMessages((current) => [...current, { role: 'user', text: question }])
    setChatInput('')
    setChatLoading(true)

    try {
      const response = await fetch('/api/agri-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          language,
          history: chatMessages.slice(-8).map((message) => ({ role: message.role, content: message.text })),
        }),
      })
      const body = await response.json().catch(() => ({
        answer: language === 'ta'
          ? 'தயவுசெய்து மீண்டும் கேளுங்கள். விவசாய ஆலோசனையை தயாரிக்கிறேன்.'
          : 'Please ask again. I am preparing a field-ready answer.',
      }))

      if (!response.ok) throw new Error(body?.detail ?? t.apiError)

      const assistantText = body.answer || (language === 'ta' ? 'உங்கள் கேள்விக்கு விரைவான ஆலோசனை வழங்குகிறேன்.' : 'Here is a practical field answer.')
      setAssistantMode(body.assistant_mode === 'local_model' ? 'local_model' : 'local_notes')
      setChatMessages((current) => [...current, { role: 'assistant', text: assistantText }])
      speakAnswer(body.voice_text || assistantText)
    } catch (requestError) {
      const msg = requestError instanceof Error ? requestError.message : t.apiError
      setChatMessages((current) => [...current, { role: 'assistant', text: msg }])
    } finally {
      setChatLoading(false)
    }
  }

  async function fetchDiseaseCare(cropId: string, symptoms: string): Promise<string> {
    const response = await fetch('/api/agri-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: `Crop: ${cropId}. Observed disease or symptoms: ${symptoms}.`,
          language,
          intent: 'disease_care',
        }),
      })
    const body = await response.json()
    if (!response.ok) throw new Error(body?.detail ?? t.apiError)
    if (typeof body.answer !== 'string' || !body.answer.trim()) {
      throw new Error(language === 'ta' ? 'ஆலோசனையைப் பெற முடியவில்லை. மீண்டும் முயற்சிக்கவும்.' : 'No guidance was returned. Please try again.')
    }
    setAssistantMode(body.assistant_mode === 'local_model' ? 'local_model' : 'local_notes')
    return body.answer
  }

  function startVoiceInput() {
    const recognitionCtor = (window as Window & {
      SpeechRecognition?: new () => SpeechRecognitionLike
      webkitSpeechRecognition?: new () => SpeechRecognitionLike
    }).SpeechRecognition ?? (window as Window & {
      webkitSpeechRecognition?: new () => SpeechRecognitionLike
    }).webkitSpeechRecognition

    if (!recognitionCtor) {
      setChatMessages((current) => [
        ...current,
        { role: 'assistant', text: t.voiceUnavailable },
      ])
      return
    }

    const recognition = new recognitionCtor() as SpeechRecognitionLike
    recognition.lang = language === 'ta' ? 'ta-IN' : 'en-US'
    recognition.interimResults = false
    recognition.continuous = false

    let finalTranscript = ''
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript ?? ''
      if (transcript) {
        finalTranscript = transcript
        setChatInput(transcript)
      }
    }

    recognition.onerror = () => setIsListening(false)
    recognition.onend = () => {
      setIsListening(false)
      const question = finalTranscript.trim()
      if (question) {
        setChatInput(question)
        void askAssistant(question)
      }
    }
    setIsListening(true)
    recognition.start()
  }

  async function identifyCrop() {
    if (!photo) return
    setAnalyzing(true)
    setError(null)
    setPrediction(null)
    setScanDiseaseAnswer('')
    setScanDiseaseError('')
    setScanDiseaseLoading(false)
    const formData = new FormData()
    formData.append('image', photo)

    try {
      const response = await fetch('/api/predict', { method: 'POST', body: formData })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) {
        const code = typeof body.detail === 'object' ? body.detail?.code : undefined
        const detail = typeof body.detail === 'string' ? body.detail : null
        throw new Error(code === 'MODEL_NOT_READY' ? t.modelNote : detail ?? t.apiError)
      }
      const result = body as Prediction
      setPrediction(result)
      if (result.status === 'identified' && result.disease && result.crop) {
        setScanDiseaseLoading(true)
        try {
          const advice = await fetchDiseaseCare(result.crop, `Leaf scan detected ${result.disease}.`)
          setScanDiseaseAnswer(advice)
        } catch (requestError) {
          setScanDiseaseError(requestError instanceof Error ? requestError.message : t.apiError)
        } finally {
          setScanDiseaseLoading(false)
        }
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t.apiError)
    } finally {
      setAnalyzing(false)
    }
  }

  async function loadWeather() {
    setWeatherLoading(true)
    setWeatherError('')
    if (!navigator.geolocation) {
      setWeatherError('Location is unavailable in this browser. You can still set your district in My farm.')
      setWeatherLoading(false)
      return
    }
    navigator.geolocation.getCurrentPosition(async ({ coords }) => {
      try {
        const params = new URLSearchParams({
          latitude: String(coords.latitude), longitude: String(coords.longitude),
          current: 'temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m',
          daily: 'temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code',
          timezone: 'auto', forecast_days: '5',
        })
        const response = await fetch(`https://api.open-meteo.com/v1/forecast?${params}`)
        if (!response.ok) throw new Error('Weather service is unavailable right now.')
        const data = await response.json()
        setWeather({
          temperature: data.current.temperature_2m,
          humidity: data.current.relative_humidity_2m,
          rain: data.current.precipitation,
          wind: data.current.wind_speed_10m,
          code: data.current.weather_code,
          days: data.daily.time.map((date: string, index: number) => ({
            date,
            min: data.daily.temperature_2m_min[index],
            max: data.daily.temperature_2m_max[index],
            rain: data.daily.precipitation_probability_max[index],
            code: data.daily.weather_code[index],
          })),
        })
        setLocationName(farmProfile.district || 'Your current location')
      } catch (requestError) {
        setWeatherError(requestError instanceof Error ? requestError.message : 'Could not load the forecast.')
      } finally {
        setWeatherLoading(false)
      }
    }, () => {
      setWeatherError('Allow location access to load local weather, or add your district under My farm.')
      setWeatherLoading(false)
    }, { enableHighAccuracy: false, timeout: 12000, maximumAge: 600000 })
  }

  function recommendCrops() {
    const soil = farmProfile.soil
    const water = farmProfile.water
    const ranked = cropGuides.map((guide) => {
      let score = guide.soils.includes(soil) ? 3 : 0
      if (water === 'limited' && guide.water === 'low') score += 2
      if (water === 'reliable' && guide.water === 'high') score += 1
      if (weather && weather.days.some((day) => day.rain > 60) && guide.water === 'high') score -= 1
      return { id: guide.id, score }
    }).sort((first, second) => second.score - first.score)
    setRecommendations(ranked.slice(0, 4).map((item) => item.id))
  }

  async function addReminder(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!reminderDue) return
    if ('Notification' in window && Notification.permission === 'default') {
      await Notification.requestPermission()
    }
    const reminder: FarmReminder = {
      id: crypto.randomUUID(), crop: reminderCrop, task: reminderTask,
      due: new Date(reminderDue).toISOString(), note: reminderNote.trim(), done: false, notified: false,
    }
    if (user) {
      try {
        const { firebaseDb, firestoreApi } = await import('./firebase')
        if (!firebaseDb) throw new Error('Firebase Firestore is unavailable.')
        await firestoreApi.setDoc(firestoreApi.doc(firebaseDb, 'users', user.uid, 'reminders', reminder.id), reminder)
        setStorageError('')
      } catch {
        setStorageError('Could not save this task to Firebase. Check your Firestore rules.')
        return
      }
    } else {
      setReminders((current) => [reminder, ...current])
    }
    setReminderNote('')
    setReminderDue(localDateTime())
  }

  async function toggleReminder(reminder: FarmReminder) {
    const updatedReminder = { ...reminder, done: !reminder.done }
    if (user) {
      try {
        const { firebaseDb, firestoreApi } = await import('./firebase')
        if (!firebaseDb) throw new Error('Firebase Firestore is unavailable.')
        await firestoreApi.setDoc(firestoreApi.doc(firebaseDb, 'users', user.uid, 'reminders', reminder.id), updatedReminder)
        setStorageError('')
      } catch {
        setStorageError('Could not update this task in Firebase.')
      }
      return
    }
    setReminders((current) => current.map((item) => item.id === reminder.id ? updatedReminder : item))
  }

  async function deleteReminder(reminderId: string) {
    if (user) {
      try {
        const { firebaseDb, firestoreApi } = await import('./firebase')
        if (!firebaseDb) throw new Error('Firebase Firestore is unavailable.')
        await firestoreApi.deleteDoc(firestoreApi.doc(firebaseDb, 'users', user.uid, 'reminders', reminderId))
        setStorageError('')
      } catch {
        setStorageError('Could not delete this task from Firebase.')
      }
      return
    }
    setReminders((current) => current.filter((item) => item.id !== reminderId))
  }

  const crop = prediction?.crop
    ? crops.find((item) => item.id === prediction.crop)
    : null
  const visibleCrops = crops.filter((item) => supportedCrops.includes(item.id))
  const supportedCountLabel = language === 'ta'
    ? `${visibleCrops.length} பயிர்கள்`
    : `${visibleCrops.length} crops`
  const diseaseLabel = prediction?.disease?.replaceAll('-', ' ') ?? null
  const upcomingReminders = reminders.filter((reminder) => !reminder.done).sort((first, second) => first.due.localeCompare(second.due))
  const activeTitle = ({
    home: 'Your farm', scan: 'Leaf health', assistant: 'Ask Uzhavan',
    weather: 'Local weather', farm: 'Farm profile', reminders: 'Field tasks',
  } satisfies Record<Tab, string>)[activeTab]
  const activeSubtitle = ({
    home: 'Field guidance, weather, and daily tasks.',
    scan: 'Identify a crop and check leaf health.',
    assistant: 'Practical answers for everyday field questions.',
    weather: 'Local conditions and a five-day forecast.',
    farm: 'Save field details for crop suggestions.',
    reminders: 'Schedule and track important farm work.',
  } satisfies Record<Tab, string>)[activeTab]

  useEffect(() => {
    if (!chatEndRef.current) return
    chatEndRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  if (isBooting) {
    return <div className="launch-screen"><div className="launch-mark"><Sprout size={28} /></div><p>UZHAVAN</p><span>Growing with you</span><div className="launch-progress"><i /></div></div>
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#home" aria-label="Uzhavan home">
          <span className="brand-mark"><Sprout size={21} strokeWidth={2.2} /></span>
          <span>uzhavan<span className="brand-period">.</span></span>
        </a>
        <div className="topbar-right">
          <span className={`service-state ${modelReady ? 'is-ready' : ''}`}>
            <span className="state-dot" />
            <span>{!apiOnline ? t.serviceOffline : modelReady ? t.modelReady : t.modelMissing}</span>
          </span>
          {user ? (
            <button className="account-button" type="button" onClick={() => void signOutUser()} title={`Sign out ${user.email ?? ''}`}>
              {user.email?.split('@')[0] || 'Account'}
            </button>
          ) : (
            <button className="account-button" type="button" onClick={() => { setAuthError(''); setShowAuth(true) }}>
              Sign in
            </button>
          )}
          <div className="language-switch" role="group" aria-label="Language">
            <button
              type="button"
              className={language === 'en' ? 'selected' : ''}
              aria-pressed={language === 'en'}
              onClick={() => setLanguage('en')}
            >EN</button>
            <button
              type="button"
              className={language === 'ta' ? 'selected' : ''}
              aria-pressed={language === 'ta'}
              onClick={() => setLanguage('ta')}
            >தமிழ்</button>
          </div>
        </div>
      </header>

      <nav className="main-nav" aria-label="Main navigation">
        {tabItems.map(({ id, label, icon: Icon }) => (
          <button key={id} type="button" className={activeTab === id ? 'active' : ''} onClick={() => setActiveTab(id)} aria-current={activeTab === id ? 'page' : undefined}>
            <Icon size={17} /><span>{label}</span>
          </button>
        ))}
      </nav>

      {storageError && <div className="storage-notice" role="alert">{storageError}</div>}

      {showAuth && <div className="auth-backdrop" role="presentation" onMouseDown={(event) => {
        if (event.target === event.currentTarget) setShowAuth(false)
      }}>
        <section className="auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-title">
          <button className="auth-close" type="button" onClick={() => setShowAuth(false)} aria-label="Close sign in"><X size={18} /></button>
          <p className="eyebrow"><span className="eyebrow-line" />UZHAVAN ACCOUNT</p>
          <h2 id="auth-title">{authMode === 'signin' ? 'Welcome back' : 'Create your account'}</h2>
          <p className="auth-description">Keep your farm details and tasks private to your account.</p>
          <form className="auth-form" onSubmit={(event) => void submitAuthentication(event)}>
            <label>Email<input type="email" value={authEmail} onChange={(event) => setAuthEmail(event.target.value)} autoComplete="email" required /></label>
            <label>Password<input type="password" value={authPassword} onChange={(event) => setAuthPassword(event.target.value)} autoComplete={authMode === 'signin' ? 'current-password' : 'new-password'} minLength={6} required /></label>
            {authError && <p className="inline-error" role="alert">{authError}</p>}
            <button className="button button-primary" type="submit" disabled={authLoading}>
              {authLoading ? <LoaderCircle className="spin" size={16} /> : null}
              {authMode === 'signin' ? 'Sign in with email' : 'Create account'}
            </button>
          </form>
          <div className="auth-divider"><span>or</span></div>
          <button className="button button-quiet auth-google" type="button" onClick={() => void signInWithGoogle()} disabled={authLoading}>
            <span className="google-mark">G</span>Continue with Google
          </button>
          <button className="auth-switch" type="button" onClick={() => {
            setAuthMode((mode) => mode === 'signin' ? 'signup' : 'signin')
            setAuthError('')
          }}>
            {authMode === 'signin' ? 'New to Uzhavan? Create an account' : 'Already have an account? Sign in'}
          </button>
          {!isFirebaseConfigured && <p className="auth-setup-note">Firebase setup is required before account sign-in can work.</p>}
        </section>
      </div>}

      <main id="home" className="main-content">
        <section className="page-heading">
          <div>
            <p className="eyebrow"><span className="eyebrow-line" />UZHAVAN FIELD DESK</p>
            <h1>{activeTab === 'home' ? 'Grow with confidence.' : activeTitle}</h1>
            <p className="page-subtitle">{activeSubtitle}</p>
          </div>
          <span className="crop-count"><Leaf size={15} />{supportedCountLabel}</span>
        </section>

        {activeTab !== 'home' && !apiOnline && activeTab === 'scan' && (
          <div className="model-notice" role="status">
            <AlertCircle size={17} />
            <span>{t.apiOfflineNote}</span>
          </div>
        )}

        {activeTab === 'scan' && apiOnline && !modelReady && (
          <div className="model-notice" role="status">
            <AlertCircle size={17} />
            <span>{t.modelNote}</span>
          </div>
        )}

        {activeTab === 'home' && (
          <section className="dashboard-view">
            <div className="welcome-banner">
              <div><span className="welcome-label"><Sprout size={14} /> TODAY</span><h2>{farmProfile.farmName || 'Welcome to your farm.'}</h2><p>{farmProfile.district ? `${farmProfile.district} · ${farmProfile.area || 'Add land size'} ${farmProfile.area ? 'acres' : ''}` : 'Add your farm details for tailored guidance.'}</p></div>
              <button type="button" className="welcome-action" onClick={() => setActiveTab(farmProfile.soil ? 'weather' : 'farm')}>Plan today <ChevronRight size={16} /></button>
            </div>
            <div className="dashboard-grid">
              <button type="button" className="dashboard-card scan-card" onClick={() => setActiveTab('scan')}><span className="dashboard-card-icon"><ScanLine size={21} /></span><span className="dashboard-card-label">LEAF HEALTH</span><strong>Scan a leaf</strong><small>Identify crops and see disease precautions</small><ChevronRight className="dashboard-arrow" size={16} /></button>
              <button type="button" className="dashboard-card weather-card" onClick={() => setActiveTab('weather')}><span className="dashboard-card-icon"><CloudSun size={21} /></span><span className="dashboard-card-label">LOCAL FORECAST</span><strong>{weather ? `${Math.round(weather.temperature)}° · ${weatherDescription(weather.code)}` : 'Check your weather'}</strong><small>{weather ? locationName : 'Rain and temperature for your location'}</small><ChevronRight className="dashboard-arrow" size={16} /></button>
              <button type="button" className="dashboard-card advisor-card" onClick={() => setActiveTab('assistant')}><span className="dashboard-card-icon"><MessageCircle size={21} /></span><span className="dashboard-card-label">ADVISOR</span><strong>Ask Uzhavan</strong><small>Voice or text, English or Tamil</small><ChevronRight className="dashboard-arrow" size={16} /></button>
              <button type="button" className="dashboard-card task-card" onClick={() => setActiveTab('reminders')}><span className="dashboard-card-icon"><CalendarDays size={21} /></span><span className="dashboard-card-label">UP NEXT</span><strong>{upcomingReminders.length ? `${upcomingReminders.length} farm task${upcomingReminders.length > 1 ? 's' : ''}` : 'No reminders set'}</strong><small>{upcomingReminders[0] ? `${upcomingReminders[0].task} · ${new Date(upcomingReminders[0].due).toLocaleDateString()}` : 'Set an alarm for irrigation or feeding'}</small><ChevronRight className="dashboard-arrow" size={16} /></button>
            </div>
            <div className="dashboard-lower"><section className="field-note"><div className="section-title"><span className="section-icon"><MapPinned size={18} /></span><div><span className="dashboard-card-label">FIELD PLAN</span><h3>Crop suggestions for your soil</h3></div></div><p>Save your soil, water access, and field size to get a crop shortlist.</p><button type="button" className="text-action" onClick={() => setActiveTab('farm')}>Add farm details <ChevronRight size={15} /></button></section><section className="today-reminders"><div className="section-title"><span className="section-icon warm"><Bell size={18} /></span><div><span className="dashboard-card-label">TASKS</span><h3>Stay on schedule</h3></div></div><p>Set reminders for irrigation, scouting, and field work.</p><button type="button" className="text-action" onClick={() => setActiveTab('reminders')}>View tasks <ChevronRight size={15} /></button></section></div>
          </section>
        )}

        {activeTab === 'scan' && <>
        <section className="work-area" aria-label={t.photoTitle}>
          <div className="capture-panel">
            <div className="panel-heading">
              <div className="step-number">01</div>
              <div>
                <h2>{t.photoTitle}</h2>
                <p>{t.photoHint}</p>
              </div>
            </div>

            <div className={`photo-stage ${previewUrl || cameraOpen ? 'has-media' : ''}`}>
              {cameraOpen ? (
                <>
                  <video ref={videoRef} autoPlay muted playsInline aria-label={t.camera} />
                  {cameraError && (
                    <div className="stage-message camera-message">
                      <AlertCircle size={25} />
                      <p>{t.cameraDenied}</p>
                    </div>
                  )}
                  <span className="camera-live"><span />LIVE</span>
                </>
              ) : previewUrl ? (
                <>
                  <img className="photo-preview" src={previewUrl} alt="Selected leaf" />
                  <button className="remove-photo icon-button" type="button" onClick={clearPhoto} aria-label={t.retake} title={t.retake}>
                    <X size={17} />
                  </button>
                  <span className="image-tag"><Check size={13} /> PHOTO READY</span>
                </>
              ) : (
                <div className="stage-message">
                  <div className="leaf-emblem"><Leaf size={37} strokeWidth={1.4} /></div>
                  <p>{t.photoHint}</p>
                  <span className="stage-corner corner-top-left" />
                  <span className="stage-corner corner-top-right" />
                  <span className="stage-corner corner-bottom-left" />
                  <span className="stage-corner corner-bottom-right" />
                </div>
              )}
            </div>

            {cameraOpen ? (
              <div className="capture-controls">
                <button className="button button-quiet" type="button" onClick={() => setFacingMode((mode) => mode === 'environment' ? 'user' : 'environment')} title={t.switchCamera} aria-label={t.switchCamera}>
                  <ArrowLeftRight size={17} />
                </button>
                <button className="button button-primary shutter-button" type="button" onClick={capturePhoto} disabled={cameraError}>
                  <Camera size={17} />{t.capture}
                </button>
                <button className="button button-quiet" type="button" onClick={() => setCameraOpen(false)} title={t.retake} aria-label={t.retake}>
                  <X size={17} />
                </button>
              </div>
            ) : (
              <div className="capture-controls">
                <label className="button button-quiet upload-button">
                  <Upload size={17} />{previewUrl ? t.useAnother : t.upload}
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={(event) => {
                      acceptPhoto(event.currentTarget.files?.[0])
                      event.currentTarget.value = ''
                    }}
                  />
                </label>
                <button className="button button-primary" type="button" onClick={openCamera}>
                  <Camera size={17} />{t.camera}
                </button>
              </div>
            )}

            <div className="privacy-note"><ShieldCheck size={14} />{t.privacy}</div>
          </div>

          <aside className="result-panel" aria-live="polite">
            <div className="result-topline">
              <span className="result-kicker">{t.resultTitle}</span>
              <ScanLine size={18} />
            </div>

            {prediction?.status === 'identified' && crop ? (
              <div className="result-content result-identified">
                <div className="result-icon success-icon"><Check size={22} /></div>
                <p className="result-caption">{t.sure}</p>
                <h2>{language === 'ta' ? crop.ta : crop.en}</h2>
                <p className="crop-translation">{language === 'ta' ? crop.en : crop.ta}</p>
                <p className={`condition-label ${prediction.disease ? 'condition-disease' : 'condition-healthy'}`}>
                  <span className="condition-marker" />
                  {prediction.disease ? `${t.diseaseDetected}: ${diseaseLabel}` : t.healthyLeaf}
                </p>
                <div className="confidence-block">
                  <div className="confidence-label"><span>{t.confidence}</span><strong>{Math.round(prediction.confidence * 100)}%</strong></div>
                  <div className="confidence-track"><span style={{ width: `${Math.max(0, Math.min(100, prediction.confidence * 100))}%` }} /></div>
                </div>
              </div>
            ) : prediction?.status === 'not_sure' ? (
              <div className="result-content result-uncertain">
                <div className="result-icon uncertain-icon"><CircleHelp size={23} /></div>
                <h2>{t.notSure}</h2>
                <p>{t.notSureHint}</p>
              </div>
            ) : analyzing ? (
              <div className="result-content result-empty">
                <div className="result-icon loading-icon"><LoaderCircle size={23} /></div>
                <h2>{t.analyzing}</h2>
                <p><span className="loading-dots">● ● ●</span></p>
              </div>
            ) : (
              <div className="result-content result-empty">
                <div className="result-icon"><ImagePlus size={22} /></div>
                <h2>{t.waitingTitle}</h2>
                <p>{t.waitingHint}</p>
                <ChevronDown className="result-arrow" size={17} />
              </div>
            )}

            {error && <p className="inline-error" role="alert"><AlertCircle size={15} />{error}</p>}

            <button className="button button-analyze" type="button" onClick={identifyCrop} disabled={!photo || !apiOnline || !modelReady || analyzing}>
              {analyzing ? <LoaderCircle className="spin" size={18} /> : <ScanLine size={18} />}
              {analyzing ? t.analyzing : t.analyze}
            </button>
            {apiOnline && !modelReady && <p className="button-footnote">Model setup required</p>}
          </aside>
        </section>

        {prediction?.status === 'identified' && prediction.disease && <section className="scan-disease-guidance" aria-live="polite">
          <div className="scan-disease-heading">
            <ShieldCheck size={19} />
            <h2>{t.diseaseResultTitle}</h2>
          </div>
          {scanDiseaseLoading && <p>{t.diseaseLoading}</p>}
          {scanDiseaseError && <p className="inline-error" role="alert"><AlertCircle size={15} />{scanDiseaseError}</p>}
          {scanDiseaseAnswer && <p className="scan-disease-answer">{scanDiseaseAnswer}</p>}
          <p className="assistant-disclaimer">{t.diseaseDisclaimer}</p>
        </section>}

        <section className="crop-list" aria-label={t.supported}>
          <div className="crop-list-heading">
            <p className="eyebrow"><span className="eyebrow-line" />{t.supported}</p>
            <span>01 — {String(visibleCrops.length).padStart(2, '0')}</span>
          </div>
          <div className="crop-items">
            {visibleCrops.map((item, index) => (
              <div className="crop-item" key={item.id}>
                <span className="crop-index">0{index + 1}</span>
                <span className="crop-name">{language === 'ta' ? item.ta : item.en}</span>
              </div>
            ))}
          </div>
        </section>
        </>}

        {activeTab === 'assistant' && <section className="assistant-panel" aria-label={t.assistantTitle}>
          <div className="assistant-header">
            <div>
              <p className="eyebrow"><span className="eyebrow-line" />{t.assistantTitle}</p>
              <h2>{t.assistantSubtitle}</h2>
            </div>
            <button type="button" className="voice-button" onClick={startVoiceInput} disabled={isListening}>
              {isListening ? <Mic size={16} className="spin" /> : isSpeaking ? <Volume2 size={16} className="voice-active" /> : <Mic size={16} />}
              {isListening ? t.listening : isSpeaking ? 'Speaking' : 'Talk to Uzhavan'}
            </button>
          </div>
          <p className={`assistant-mode ${assistantMode === 'local_model' ? 'mode-connected' : ''}`}>
            {assistantMode === 'local_model'
              ? 'AI model connected'
              : 'AI offline · Showing saved guidance'}
          </p>

          <div className="chat-box">
            {chatMessages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`chat-message ${message.role}`}>
                <span className="chat-role">{message.role === 'assistant' ? 'Uzhavan AI' : 'You'}</span>
                <p>{message.text}</p>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          <div className="chat-input-row">
            <input
              type="text"
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void askAssistant()
              }}
              placeholder={t.assistantPlaceholder}
              aria-label={t.assistantTitle}
            />
            <button type="button" className="icon-action mic-action" onClick={startVoiceInput} disabled={isListening} aria-label={isListening ? t.listening : 'Ask by voice'} title="Ask by voice">
              {isListening ? <LoaderCircle className="spin" size={18} /> : <Mic size={18} />}
            </button>
            <button type="button" className="button button-primary" onClick={() => void askAssistant()} disabled={chatLoading || !chatInput.trim()}>
              {chatLoading ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />}{t.send}
            </button>
          </div>
          <p className="assistant-disclaimer">Confirm pesticide and fertilizer use with your local agriculture office.</p>
        </section>}

        {activeTab === 'weather' && <section className="tool-page weather-view">
          <div className="tool-heading"><div><p className="eyebrow"><span className="eyebrow-line" />WEATHER</p><h2>{locationName}</h2><p>Enable location for your local forecast.</p></div><button className="button button-primary" type="button" onClick={() => void loadWeather()} disabled={weatherLoading}>{weatherLoading ? <LoaderCircle size={16} className="spin" /> : <MapPin size={16} />}{weatherLoading ? 'Loading…' : 'Use my location'}</button></div>
          {weatherError && <p className="inline-error" role="alert">{weatherError}</p>}
          {weather ? <><div className="weather-summary"><div className="temperature-readout"><CloudSun size={38} /><div><strong>{Math.round(weather.temperature)}°</strong><span>{weatherDescription(weather.code)}</span></div></div><div className="weather-metric"><Droplets size={18} /><span>Humidity</span><strong>{weather.humidity}%</strong></div><div className="weather-metric"><CloudRain size={18} /><span>Rain now</span><strong>{weather.rain} mm</strong></div><div className="weather-metric"><Wind size={18} /><span>Wind</span><strong>{Math.round(weather.wind)} km/h</strong></div></div><div className="forecast-list">{weather.days.map((day, index) => <div className="forecast-day" key={day.date}><span>{index === 0 ? 'Today' : new Date(`${day.date}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' })}</span><CloudSun size={18} /><strong>{Math.round(day.max)}° <span>{Math.round(day.min)}°</span></strong><small><CloudRain size={13} />{day.rain}% rain</small></div>)}</div><p className="weather-note"><ThermometerSun size={16} />Check soil moisture before irrigation. Follow local spray advisories.</p></> : <div className="empty-tool"><div className="empty-tool-icon"><CloudSun size={28} /></div><h3>Local forecast</h3><p>Current conditions and a five-day outlook.</p><button className="button button-primary" type="button" onClick={() => void loadWeather()} disabled={weatherLoading}>{weatherLoading ? 'Loading…' : 'Enable location'}</button></div>}
        </section>}

        {activeTab === 'farm' && <section className="tool-page farm-view">
          <div className="tool-heading"><div><p className="eyebrow"><span className="eyebrow-line" />FARM DETAILS</p><h2>Plan for your farm</h2><p>Add field details for crop suggestions.</p></div><span className="private-tag"><ShieldCheck size={15} />{user ? storageReady ? 'Synced to your account' : 'Syncing…' : 'Saved on this device'}</span></div>
          <div className="farm-form-grid"><label>Farm name<input disabled={Boolean(user && !storageReady)} value={farmProfile.farmName} onChange={(event) => setFarmProfile({ ...farmProfile, farmName: event.target.value })} placeholder="e.g. North field" /></label><label>District<input disabled={Boolean(user && !storageReady)} value={farmProfile.district} onChange={(event) => setFarmProfile({ ...farmProfile, district: event.target.value })} placeholder="Your district" /></label><label>Area (acres)<input disabled={Boolean(user && !storageReady)} inputMode="decimal" type="number" min="0" value={farmProfile.area} onChange={(event) => setFarmProfile({ ...farmProfile, area: event.target.value })} placeholder="e.g. 2.5" /></label><label>Soil type<select disabled={Boolean(user && !storageReady)} value={farmProfile.soil} onChange={(event) => setFarmProfile({ ...farmProfile, soil: event.target.value })}><option value="loam">Loamy</option><option value="clay">Clay</option><option value="black">Black cotton soil</option><option value="red">Red soil</option><option value="sandy">Sandy</option><option value="alluvial">Alluvial</option></select></label><label>Water access<select disabled={Boolean(user && !storageReady)} value={farmProfile.water} onChange={(event) => setFarmProfile({ ...farmProfile, water: event.target.value })}><option value="reliable">Reliable irrigation</option><option value="seasonal">Seasonal / rainfall-led</option><option value="limited">Limited water</option></select></label></div>
          <button className="button button-primary recommend-button" type="button" onClick={recommendCrops} disabled={Boolean(user && !storageReady)}><Sprout size={17} />Suggest crops</button>
          {recommendations.length > 0 && <div className="recommendation-results"><div className="section-title"><span className="section-icon"><Sprout size={18} /></span><div><span className="dashboard-card-label">CROP SUGGESTIONS</span><h3>Options for {farmProfile.soil} soil</h3></div></div><div className="recommendation-grid">{recommendations.map((id, index) => { const crop = crops.find((item) => item.id === id); const guide = cropGuides.find((item) => item.id === id); return <article className="recommendation-item" key={id}><span>0{index + 1}</span><div><h4>{crop?.en}</h4><p>{guide?.reason}<br /><strong>Irrigation:</strong> {irrigationMethods[id]}</p></div><span className="water-need">{guide?.water} water</span></article> })}</div><p className="recommendation-caveat">Confirm the season, water, seed availability, and market locally before planting.</p></div>}
        </section>}

        {activeTab === 'reminders' && <section className="tool-page reminders-view">
          <div className="tool-heading"><div><p className="eyebrow"><span className="eyebrow-line" />FIELD TASKS</p><h2>Plan your next task</h2><p>Set reminders for irrigation, scouting, and more.</p></div><span className="private-tag"><Bell size={15} />{upcomingReminders.length} upcoming</span></div>
          <form className="reminder-form" onSubmit={(event) => void addReminder(event)}><label>Crop<select disabled={Boolean(user && !storageReady)} value={reminderCrop} onChange={(event) => setReminderCrop(event.target.value)}>{crops.map((crop) => <option value={crop.id} key={crop.id}>{crop.en}</option>)}</select></label><label>Task<select disabled={Boolean(user && !storageReady)} value={reminderTask} onChange={(event) => setReminderTask(event.target.value)}><option>Water / irrigation</option><option>Fertilizer application</option><option>Field scouting</option><option>Weed control</option><option>Harvest check</option><option>Other field task</option></select></label><label>Time<input disabled={Boolean(user && !storageReady)} type="datetime-local" value={reminderDue} onChange={(event) => setReminderDue(event.target.value)} required /></label><label className="reminder-note">Note (optional)<input disabled={Boolean(user && !storageReady)} value={reminderNote} onChange={(event) => setReminderNote(event.target.value)} placeholder="Growth stage, amount, or field section" /></label><button className="button button-primary" type="submit" disabled={Boolean(user && !storageReady)}><Bell size={16} />Set reminder</button></form>
          <p className="care-guidance"><Sprout size={16} />{cropCareGuides[reminderCrop] ?? cropCareGuides.corn_general}</p>
          <div className="reminder-list"><div className="crop-list-heading"><p className="eyebrow"><span className="eyebrow-line" />YOUR SCHEDULE</p><span>{reminders.length} saved</span></div>{reminders.length ? reminders.slice().sort((first, second) => first.due.localeCompare(second.due)).map((reminder) => <article className={`reminder-item ${reminder.done ? 'is-done' : ''}`} key={reminder.id}><button type="button" className="reminder-check" disabled={Boolean(user && !storageReady)} onClick={() => void toggleReminder(reminder)} aria-label={reminder.done ? 'Mark as not done' : 'Mark as done'}>{reminder.done && <Check size={14} />}</button><div className="reminder-details"><strong>{reminder.task} · {reminder.crop}</strong><span><CalendarDays size={13} />{new Date(reminder.due).toLocaleString()}</span>{reminder.note && <p>{reminder.note}</p>}</div><button type="button" className="remove-reminder" disabled={Boolean(user && !storageReady)} onClick={() => void deleteReminder(reminder.id)} aria-label="Delete reminder"><X size={16} /></button></article>) : <div className="empty-reminders"><CalendarDays size={24} /><p>Your crop-care reminders will appear here.</p></div>}</div>
          <p className="weather-note"><AlertCircle size={16} />Irrigation and fertilizer schedules depend on crop stage, recent rain, and soil tests. Set reminders from your local crop calendar rather than using a generic date.</p>
        </section>}
      </main>

      <footer className="app-footer">
        <span>UZHAVAN <span className="footer-dot">/</span> FIELD TOOLS</span>
        <span>BUILT FOR THE GROWING SEASON <Sprout size={14} /></span>
      </footer>
    </div>
  )
}

export default App
