import { create } from "zustand";

const useAlertStore = create((set) => ({
    notifications: [],

    addNotification: (msg) =>
        set((state) => ({
            notifications: [msg, ...state.notifications],
        })),

    clearNotifications: () =>
        set({ notifications: [] }),
}));

export default useAlertStore;