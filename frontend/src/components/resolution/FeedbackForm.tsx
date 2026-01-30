import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { Star, Send, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    Form,
    FormControl,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

const feedbackSchema = z.object({
    rating: z.number().min(1).max(5),
    feedback: z.string().min(10, {
        message: "Feedback must be at least 10 characters.",
    }),
    mistakes: z.string().optional(),
});

interface FeedbackFormProps {
    resolutionId: string;
    conflictId?: string;
    onSuccess?: () => void;
    onCancel?: () => void;
}

export function FeedbackForm({ resolutionId, conflictId: propConflictId, onSuccess, onCancel }: FeedbackFormProps) {
    const [isSubmitting, setIsSubmitting] = useState(false);

    const form = useForm<z.infer<typeof feedbackSchema>>({
        resolver: zodResolver(feedbackSchema),
        defaultValues: {
            rating: 0,
            feedback: "",
            mistakes: "",
        },
    });

    async function onSubmit(values: z.infer<typeof feedbackSchema>) {
        setIsSubmitting(true);
        try {
            // Try to get conflictId from props or location as fallback
            let conflictId = propConflictId;

            if (!conflictId) {
                try {
                    // Try to get from location.state.activeConflict
                    const loc = window.location;
                    if (loc && (loc as any).state && (loc as any).state.activeConflict) {
                        conflictId = (loc as any).state.activeConflict.conflict_id;
                    }
                } catch { }
            }

            const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8002'}/api/feedback`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    conflict_id: conflictId, // will be null/undefined if not found
                    resolution_id: resolutionId,
                    rating: values.rating,
                    feedback: values.feedback,
                    mistakes: values.mistakes,
                }),
            });

            if (!response.ok) {
                throw new Error("Failed to submit feedback");
            }

            toast.success("Thank you for your feedback! The agent has learned from this interaction.");
            onSuccess?.();
        } catch (error) {
            toast.error("Failed to submit feedback. Please try again.");
            console.error("Feedback error:", error);
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <div className="space-y-4 p-4 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 rounded-xl border border-primary/20 shadow-2xl max-w-md w-full animate-in fade-in slide-in-from-bottom-4 duration-300">
            <div className="flex items-center justify-between mb-2">
                <h3 className="font-bold text-lg flex items-center gap-2">
                    <Send className="w-4 h-4 text-primary" />
                    Improve AI Agent
                </h3>
                {onCancel && (
                    <Button variant="ghost" size="icon" onClick={onCancel} className="h-8 w-8">
                        <X className="w-4 h-4" />
                    </Button>
                )}
            </div>

            <p className="text-sm text-muted-foreground mb-4">
                Help our agent learn from its mistakes. Your feedback directly impacts future resolution quality.
            </p>

            <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                    <FormField
                        control={form.control}
                        name="rating"
                        render={({ field }) => (
                            <FormItem className="space-y-2">
                                <FormLabel>How accurate was this solution?</FormLabel>
                                <FormControl>
                                    <div className="flex gap-1">
                                        {[1, 2, 3, 4, 5].map((star) => (
                                            <button
                                                key={star}
                                                type="button"
                                                onClick={() => field.onChange(star)}
                                                className={`p-1 transition-transform hover:scale-125 ${field.value >= star ? "text-yellow-500 fill-yellow-500" : "text-muted-foreground"
                                                    }`}
                                            >
                                                <Star className="w-6 h-6" />
                                            </button>
                                        ))}
                                    </div>
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    <FormField
                        control={form.control}
                        name="feedback"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Detailed Feedback</FormLabel>
                                <FormControl>
                                    <Textarea
                                        placeholder="Describe what was good or what could be better..."
                                        className="min-h-[80px] bg-background/50"
                                        {...field}
                                    />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    <FormField
                        control={form.control}
                        name="mistakes"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Specific Mistakes (Optional)</FormLabel>
                                <FormControl>
                                    <Textarea
                                        placeholder="If the agent made a specific error, please detail it here."
                                        className="min-h-[60px] bg-destructive/5 border-destructive/20 focus:bg-destructive/10"
                                        {...field}
                                    />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />

                    <div className="flex gap-2 pt-2">
                        <Button
                            type="submit"
                            disabled={isSubmitting}
                            className="flex-1 gap-2 h-11 font-bold shadow-lg shadow-primary/20"
                        >
                            {isSubmitting ? "Submitting..." : "Send Feedback"}
                        </Button>
                        {onCancel && (
                            <Button
                                type="button"
                                variant="outline"
                                onClick={onCancel}
                                className="h-11"
                            >
                                Skip
                            </Button>
                        )}
                    </div>
                </form>
            </Form>
        </div>
    );
}
