import { useState, useRef } from "react";

export default function useAsyncAction() {
    const [loading, setLoading] = useState(false);
    const inProgressRef = useRef(false);

    const run = async (asyncFn) => {
        if (inProgressRef.current) return;

        inProgressRef.current = true;
        setLoading(true);

        try {
            await asyncFn();
        } finally {
            inProgressRef.current = false;
            setLoading(false);
        }
    };

    return { loading, run };
}