package com.bydmate.app.service

import android.app.DownloadManager
import android.content.Context
import android.content.ContextWrapper
import android.content.Intent
import android.database.MatrixCursor
import android.net.Uri
import android.os.Environment
import androidx.core.content.FileProvider
import androidx.test.core.app.ApplicationProvider
import com.bydmate.app.util.AppStrings
import io.mockk.every
import io.mockk.mockk
import io.mockk.slot
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import okhttp3.OkHttpClient
import okhttp3.Response
import okhttp3.Protocol
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowEnvironment
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29])
class ForkUpdateTest {
    private val context: Context = ApplicationProvider.getApplicationContext()

    private fun checker(json: String, status: Int = 200): UpdateChecker {
        val client = OkHttpClient.Builder().addInterceptor { chain ->
            assertEquals("https://api.github.com/repos/Dmitrijsmok/BYDMate/releases/latest", chain.request().url.toString())
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1)
                .code(status).message("test").body(json.toResponseBody("application/json".toMediaType())).build()
        }.build()
        return UpdateChecker(client, mockk<AppStrings>(relaxed = true))
    }

    @Test fun `only the exact fork asset is selected`() = runTest {
        val url = "https://github.com/Dmitrijsmok/BYDMate/releases/download/v99.0.0/BYDMate-dilink3-v99.0.0.apk"
        val json = """{"tag_name":"v99.0.0","assets":[
            {"name":"BYDMate-v99.0.0.apk","browser_download_url":"https://github.com/AndyShaman/BYDMate/releases/download/v99.0.0/BYDMate-v99.0.0.apk"},
            {"name":"DiLink3Friendly-v99.0.0.apk","browser_download_url":"https://github.com/Dmitrijsmok/BYDMate/releases/download/v99.0.0/DiLink3Friendly-v99.0.0.apk"},
            {"name":"BYDMate-dilink3-v99.0.0.apk","browser_download_url":"$url"}]}"""
        assertEquals(url, checker(json).checkForUpdate(context, true)?.downloadUrl)
    }

    @Test fun `upstream URL with a fork filename is rejected`() = runTest {
        val json = """{"tag_name":"v99.0.0","assets":[{"name":"BYDMate-dilink3-v99.0.0.apk",
            "browser_download_url":"https://github.com/AndyShaman/BYDMate/releases/download/v99.0.0/BYDMate-dilink3-v99.0.0.apk"}]}"""
        assertTrue(runCatching { checker(json).checkForUpdate(context, true) }.isFailure)
    }

    @Test fun `missing releases and older versions do not offer an update`() = runTest {
        assertNull(checker("{}", 404).checkForUpdate(context, true))
        assertNull(checker("""{"tag_name":"v0.0.1"}""").checkForUpdate(context, true))
    }

    @Test fun `legacy fork asset alone is not selected`() = runTest {
        val json = """{"tag_name":"v99.0.0","assets":[{"name":"DiLink3Friendly-v99.0.0.apk",
            "browser_download_url":"https://github.com/Dmitrijsmok/BYDMate/releases/download/v99.0.0/DiLink3Friendly-v99.0.0.apk"}]}"""
        assertTrue(runCatching { checker(json).checkForUpdate(context, true) }.isFailure)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test fun `download replacement destination and installer use the same new filename`() = runTest {
        Dispatchers.setMain(StandardTestDispatcher(testScheduler))
        // AndroidX caches paths across Robolectric tests; do not leak this test's temporary roots.
        @Suppress("UNCHECKED_CAST")
        val paths = FileProvider::class.java.getDeclaredField("sCache").apply { isAccessible = true }
            .get(null) as MutableMap<String, Any>
        val authority = "${context.packageName}.fileprovider"
        val previousPaths = paths.remove(authority)
        val previousPublicRoot = Environment.getExternalStoragePublicDirectory(null).toPath()
        // Match Android's public Download directory to the FileProvider external-storage root.
        ShadowEnvironment.setExternalStoragePublicDirectory(Environment.getExternalStorageDirectory().toPath())
        val file = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS),
            "BYDMate-dilink3-v1.0.1.apk")
        try {
            file.parentFile!!.mkdirs()
            file.writeText("previous partial download")
            val manager = mockk<DownloadManager>()
            val request = slot<DownloadManager.Request>()
            every { manager.enqueue(capture(request)) } answers {
                assertTrue("Previous download must be replaced", !file.exists())
                file.writeText("completed download")
                1L
            }
            every { manager.query(any()) } answers {
                MatrixCursor(arrayOf(DownloadManager.COLUMN_STATUS)).apply {
                    addRow(arrayOf(DownloadManager.STATUS_SUCCESSFUL))
                }
            }
            var installed: Intent? = null
            val downloadContext = object : ContextWrapper(context) {
                override fun getSystemService(name: String): Any? =
                    if (name == Context.DOWNLOAD_SERVICE) manager else super.getSystemService(name)
                override fun startActivity(intent: Intent) { installed = intent }
            }
            val url = "https://github.com/Dmitrijsmok/BYDMate/releases/download/v1.0.1/${file.name}"
            checker("{}").downloadAndInstall(downloadContext, UpdateChecker.UpdateInfo("1.0.1", url, ""))

            assertEquals(Uri.fromFile(file), shadowOf(request.captured).destination)
            assertEquals(Intent.ACTION_VIEW, installed?.action)
            assertEquals("application/vnd.android.package-archive", installed?.type)
            assertEquals("${context.packageName}.fileprovider", installed?.data?.authority)
            assertEquals(file.name, installed?.data?.lastPathSegment)
        } finally {
            file.delete()
            paths.remove(authority)
            if (previousPaths != null) paths[authority] = previousPaths
            ShadowEnvironment.setExternalStoragePublicDirectory(previousPublicRoot)
            Dispatchers.resetMain()
        }
    }
}
