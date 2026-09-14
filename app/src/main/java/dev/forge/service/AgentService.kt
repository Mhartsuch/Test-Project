package dev.forge.service

import android.app.Notification
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import dev.forge.MainActivity
import dev.forge.tools.AndroidTools

/** Keeps the process alive (and visible in the shade) while the agent works. */
class AgentService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        AndroidTools.ensureChannel(this)
        startForeground(NOTIF_ID, build(this, "Forge is working", "Long task in progress"))
        return START_NOT_STICKY
    }

    companion object {
        const val NOTIF_ID = 4242
        fun build(ctx: Context, title: String, text: String): Notification {
            val pi = PendingIntent.getActivity(ctx, 0, Intent(ctx, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            return NotificationCompat.Builder(ctx, AndroidTools.CHANNEL).setSmallIcon(android.R.drawable.ic_menu_manage)
                .setContentTitle(title).setContentText(text).setContentIntent(pi).setOngoing(true).setOnlyAlertOnce(true).build()
        }
        fun updateNotification(ctx: Context, title: String, text: String) {
            runCatching { (ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notify(NOTIF_ID, build(ctx, title, text)) }
        }
    }
}
